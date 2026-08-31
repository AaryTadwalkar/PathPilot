"""
extraction.py — Resume PDF parsing and AI-powered profile extraction.

Overall Design:
  Two-stage pipeline:
    Stage 1: PDF → raw text   via parse_pdf_from_bytes() using PyMuPDF.
    Stage 2: raw text → JSON  via extract_profile_data() using Gemini 2.5 Flash.

  Stage 1 uses a column-aware block extraction strategy (sorted by Y then X)
  so multi-column resume layouts are reconstructed in reading order instead of
  being interleaved.

  VISION FALLBACK: If text layer extraction yields fewer than _MIN_RESUME_TEXT_LEN
  characters (scanned / Canva / image-based PDFs), each page is rendered at 200 DPI
  as a PNG and sent to Gemini's multimodal (Vision) API which reads the image like
  OCR. This covers all real-world PDF types without requiring Tesseract installation.

  Stage 2 sends the text to Gemini with a format-flexible prompt that handles
  non-standard section headers (Work History, Technical Competencies, etc.) and
  multi-column layouts. A name fallback extracts from raw text when Gemini returns null.

Elements:
  parse_pdf_from_bytes(file_bytes)        — Stage 1: bytes → text (with vision fallback)
  _extract_text_via_vision(doc)           — Gemini Vision OCR for image-based PDFs
  _extract_first_name_from_text(text)     — Fallback: first valid name line from text
  extract_profile_data(resume_text)       — Stage 2: text → structured dict (Gemini)

Final Output:
  extract_profile_data() returns a dict matching the Pydantic UserProfileCreate
  schema with keys: name, email, college, department, graduation_year, cgpa,
  github_url, linkedin_url, career_interests, certifications, skills, projects,
  experience, experience_duration.
"""

import os
import fitz  # PyMuPDF
import json
from google import genai
from google.genai import types as genai_types
from dotenv import load_dotenv
import time
import app.services.taxonomy as taxonomy
load_dotenv()

# Initialize the Gemini client using the key from your .env file
client = genai.Client(api_key=os.getenv("GEMINI_API_KEY"))

# Minimum character count from PyMuPDF text layer to skip vision fallback.
# A 1-page resume typically yields 500–2000 chars; 150 is a very conservative floor.
# Below this threshold we switch to Gemini Vision (image rendering → multimodal API).
_MIN_RESUME_TEXT_LEN = 150


def _extract_text_via_vision(doc: fitz.Document) -> str:
    """
    Gemini Vision OCR fallback for PDFs with no text layer (scanned / Canva exports).

    How it works:
      Renders each PDF page to a PNG image at 200 DPI using PyMuPDF's Pixmap API,
      then sends all page images together to Gemini 2.5 Flash's multimodal endpoint.
      Gemini Vision reads the images like a human would and returns all visible text.
      200 DPI gives a good balance: enough resolution for accurate text reading
      without creating oversized payloads (typically 1–3 MB per page).

    Concepts:
      fitz.Matrix(scale, scale): scales page dimensions. 200/72 = ~2.78× upscale
        from PDF's default 72 DPI to 200 DPI.
      pix.tobytes('png'): encodes the rendered pixmap as PNG bytes in memory.
      genai_types.Part.from_bytes(): multimodal content part for the Gemini API.
      All pages are sent in a single API call with one instruction Part at the end.

    Used by:
      parse_pdf_from_bytes() — called when text extraction yields < _MIN_RESUME_TEXT_LEN chars.

    Returns:
      Extracted text string from all pages, or empty string if vision also fails.
    """
    try:
        parts: list[genai_types.Part] = []
        matrix = fitz.Matrix(200 / 72, 200 / 72)  # 200 DPI
        for page in doc:
            pix = page.get_pixmap(matrix=matrix)
            png_bytes = pix.tobytes("png")
            parts.append(genai_types.Part.from_bytes(data=png_bytes, mime_type="image/png"))

        # Single instruction appended after all page images
        parts.append(genai_types.Part.from_text(
            text=(
                "This is a resume. Extract ALL visible text exactly as it appears across "
                "all pages. Preserve section structure. Output plain text only, no markdown."
            )
        ))

        response = client.models.generate_content(
            model="gemini-2.5-flash",
            contents=parts,
        )
        extracted = response.text.strip()
        print(f"[extraction] Vision OCR extracted {len(extracted)} chars from {len(doc)} page(s)")
        return extracted
    except Exception as e:
        print(f"[extraction] Vision OCR fallback failed: {e}")
        return ""


def parse_pdf_from_bytes(file_bytes: bytes) -> str:
    """
    Reads a raw byte stream of a PDF file entirely in memory (no disk write),
    extracts all readable text using PyMuPDF, and returns it as a single string.

    How it works:
      Stage A — Text layer extraction:
        Uses fitz.open() with stream= (no temp file). Uses get_text("blocks")
        instead of get_text("text") for column-aware reading-order reconstruction.
        Each block tuple has (x0, y0, x1, y1, text, ...). Blocks are sorted by
        Y-band (20px bucket) then X, recreating natural reading order.

      Stage B — Vision fallback:
        If Stage A yields fewer than _MIN_RESUME_TEXT_LEN chars (image-only PDF,
        Canva export, scanned document), the function calls _extract_text_via_vision()
        which renders pages at 200 DPI and sends them to Gemini Vision for OCR.
        This covers all real-world resume formats without Tesseract installation.

    Concepts:
      PDF text blocks: logical text regions with bounding box (x0,y0,x1,y1).
      Y-bucketing: rounding y0 to 20px prevents baseline micro-differences from
        scrambling left-right sort order.

    Used by:
      upload_resume() in backend/app/main.py — calls this then passes result
      to extract_profile_data().

    Returns:
      Raw text string. Always non-empty for valid parseable PDFs (vision handles
      image-only). May be empty only if both extraction methods fail entirely.
    """
    text = ""
    doc = None
    try:
        doc = fitz.open(stream=file_bytes, filetype="pdf")
        for page in doc:
            blocks = page.get_text("blocks")
            # Sort by vertical band (20px bucket) then horizontal position.
            blocks.sort(key=lambda b: (round(b[1] / 20), b[0]))
            for block in blocks:
                block_text = block[4].strip()
                if block_text:
                    text += block_text + "\n"
            text += "\n"  # page separator
    except Exception as e:
        print(f"[extraction] PDF text layer error: {e}")

    # Vision fallback: image-only or scanned PDF
    if len(text.strip()) < _MIN_RESUME_TEXT_LEN and doc is not None:
        print("[extraction] Text layer insufficient — switching to Gemini Vision OCR")
        text = _extract_text_via_vision(doc)

    return text


def _extract_first_name_from_text(resume_text: str) -> str | None:
    """
    Fallback name extractor: returns the first non-blank, non-URL line
    from the raw PDF text (typically the candidate's name at the top).

    How it works:
      Iterates lines of extracted text and skips lines that are:
        - Empty / whitespace only
        - URLs, emails, linkedin/github references
        - Phone numbers (digit-only after stripping +, -, spaces)
        - Very long (>60 chars) — likely a headline or summary sentence
      Accepts only lines with 2+ words composed of letters/spaces/dots.

    Used by:
      extract_profile_data() as a fallback when Gemini returns null for 'name'.
      Also called in the exception handler of extract_profile_data() so at minimum
      a name is recovered even if Gemini completely fails.

    Returns:
      First matching name string, or None if not found.
    """
    for line in resume_text.splitlines():
        stripped = line.strip()
        if not stripped:
            continue
        if any(c in stripped for c in ("http", "@", "linkedin", "github")):
            continue
        if stripped.replace("+", "").replace("-", "").replace(" ", "").isdigit():
            continue  # phone number
        if len(stripped) > 60:
            continue  # likely a headline/summary, not a name
        words = stripped.split()
        if len(words) >= 2 and all(w.replace(".", "").isalpha() for w in words):
            return stripped
    return None


def extract_profile_data(resume_text: str) -> dict:
    """
    Sends raw resume text to Gemini 2.5 Flash with a format-flexible prompt that
    extracts the candidate's complete profile as strict JSON.

    How it works:
      1. Empty-text guard: if resume_text is too short, raises ValueError so the
         caller (upload_resume in main.py) can return a 400 to the frontend with
         a human-readable message instead of silently sending Gemini an empty prompt.
      2. Gemini prompt: instructs the model to handle non-standard section headers
         (Work History, Technical Competencies, Academic Background, etc.) and
         two-column layouts where text may appear non-sequentially.
      3. 3-attempt retry with 2-second sleep between attempts (rate-limit resilience).
      4. JSON cleanup: strips markdown code fences if Gemini wraps output in them.
         A second fallback regex-extracts the { ... } block if json.loads fails.
      5. Skill normalisation: passes each extracted skill through taxonomy.normalize_skill().
      6. Name fallback: if Gemini returns null for 'name', extracts from first PDF line.
      7. Certifications normalisation: coerces to list[str], strips empties.

    Concepts:
      LLM prompt engineering — format-flexible instructions reduce hallucination
        when the input doesn't match the model's training distribution.
      Defensive JSON parsing — two-pass parse with manual cleanup handles Gemini
        occasionally wrapping output in markdown fences or adding trailing commas.

    Used by:
      upload_resume() in backend/app/main.py — calls this with text from
      parse_pdf_from_bytes() and returns extracted_data to the frontend.

    Raises:
      ValueError: if resume_text is too short (empty/image PDF) — caller converts to 400.

    Returns:
      dict with all profile fields. Worst case (Gemini total failure) returns a
      minimal safe dict with name (from fallback) and empty arrays.
    """
    # ── Guard: empty text even after vision fallback ─────────────────────────
    # At this point vision has already run inside parse_pdf_from_bytes().
    # If we still have < _MIN_RESUME_TEXT_LEN, the PDF is completely unreadable.
    if len(resume_text.strip()) < _MIN_RESUME_TEXT_LEN:
        raise ValueError(
            "Could not extract text from this PDF even after attempting image OCR. "
            "The file may be encrypted, corrupted, or contain no readable content. "
            "Please try exporting your resume from Word, Google Docs, or Overleaf."
        )

    prompt = f"""
    You are an expert technical recruiter AI. Extract the candidate's COMPLETE profile from the provided resume text.

    CRITICAL INSTRUCTION FOR SKILLS:
    You must normalize skill names to their most common industry standard format.
    Examples: "React.js" -> "React", "Node" -> "Node.js", "GCP" -> "Google Cloud".

    IMPORTANT — RESUME FORMAT FLEXIBILITY:
    This resume may NOT use standard section headers. Be flexible:
    - "Work History", "Employment", "Career", or no header → treat as Experience
    - "Technical Skills", "Competencies", "Technologies", "Tech Stack" → treat as Skills
    - "Academic Background", "Qualifications", "Education Details" → treat as Education
    - If the resume uses a two-column or creative layout, text may appear out of order.
      Interpret the full content holistically, not just sequentially.
    - If there are NO formal sections, infer from context (dates → experience, bullet lists of tools → skills).

    You MUST output valid, strictly formatted JSON only. Do NOT include markdown code blocks.

    The JSON must follow this exact structure:
    {{
        "name": "Candidate Full Name",
        "email": "email@example.com",
        "college": "University Name",
        "department": "Major/Department",
        "graduation_year": 2028,
        "cgpa": 9.05,
        "github_url": "https://github.com/...",
        "linkedin_url": "https://linkedin.com/in/...",
        "career_interests": ["AI Engineer", "Data Scientist"],
        "certifications": [
            "NVIDIA Deep Learning Institute: Fundamentals of Deep Learning",
            "Oracle Cloud Infrastructure 2023 AI Certified Foundations Associate"
        ],
        "skills": [
            {{"skill": "Python", "category": "Language"}}
        ],
        "projects": [
            {{
                "name": "E-Commerce App",
                "description": "Built a full-stack web application for online shopping.",
                "domain": "Web Development",
                "skills_used": ["React", "Node.js", "MongoDB"]
            }}
        ],
        "experience": [
            "Software Engineering Intern at TechCorp"
        ],
        "experience_duration": "6 months"
    }}

    IMPORTANT:
    - For 'name': The candidate's full name is almost always the FIRST prominent element of the resume. Extract it carefully.
    - For 'certifications': Extract ALL certificates, online courses, credentials (NVIDIA, AWS, Oracle, Coursera, Google, Udemy, etc.).
    - If information is missing, use empty arrays [] or null.
    - Estimate 'experience_duration' by totaling time across tech roles.
    - For graduation year, estimate based on current year and degree level if not explicit.

    Resume Text:
    {resume_text}
    """

    try:
        for attempt in range(3):
            try:
                response = client.models.generate_content(
                    model="gemini-2.5-flash",
                    contents=prompt,
                )
                break
            except Exception as e:
                if attempt == 2:
                    raise e
                time.sleep(2)

        raw_text = response.text.strip()
        if raw_text.startswith("```json"):
            raw_text = raw_text[7:-3].strip()
        elif raw_text.startswith("```"):
            raw_text = raw_text[3:-3].strip()

        try:
            parsed_data = json.loads(raw_text)
        except Exception:
            raw_text = raw_text.strip()
            raw_text = raw_text.replace("```json", "")
            raw_text = raw_text.replace("```", "")
            raw_text = raw_text.replace(",]", "]")
            raw_text = raw_text.replace(",}", "}")
            start = raw_text.find("{")
            end = raw_text.rfind("}")
            if start != -1 and end != -1:
                raw_text = raw_text[start:end + 1]
            print("\n========== GEMINI RAW ==========\n")
            print(raw_text)
            print("\n===============================\n")
            parsed_data = json.loads(raw_text)

        # Normalize the skills extracted by Gemini
        for skill_obj in parsed_data.get("skills", []):
            raw_name = skill_obj.get("skill", "")
            skill_obj["skill"] = taxonomy.normalize_skill(raw_name)

        # --- Name fallback ---
        # If Gemini returned null/empty for name, extract from the first line of the PDF
        if not parsed_data.get("name"):
            fallback_name = _extract_first_name_from_text(resume_text)
            if fallback_name:
                parsed_data["name"] = fallback_name
                print(f"[extraction] Name fallback: used first PDF line: '{fallback_name}'")

        # --- Certifications normalisation ---
        # Ensure certifications is always a list of strings
        raw_certs = parsed_data.get("certifications")
        if raw_certs is None:
            parsed_data["certifications"] = []
        elif isinstance(raw_certs, list):
            parsed_data["certifications"] = [str(c).strip() for c in raw_certs if c and str(c).strip()]
        else:
            parsed_data["certifications"] = []

        return parsed_data

    except ValueError:
        # Re-raise the unreadable-PDF guard — caller (main.py) converts to HTTP 400
        raise
    except Exception as e:
        print(f"[extraction] Gemini Extraction Error: {e}")
        # Attempt to recover name from raw text even on extraction failure
        fallback_name = _extract_first_name_from_text(resume_text)
        return {
            "name": fallback_name,
            "skills": [], "projects": [], "experience": [],
            "certifications": [], "experience_duration": None,
        }