import { apiRequest } from "@/lib/api";

const API_BASE_URL = "http://127.0.0.1:8000";

export async function saveProfile(
  data: unknown
) {
  return apiRequest("/profile/save", {
    method: "POST",
    body: JSON.stringify(data),
  });
}

export async function getProfile(
  userId: number
) {
  return apiRequest(
    `/profile/${userId}`
  );
}

/* NEW */

export async function uploadResume(
  file: File,
  userId: number
) {
  const formData = new FormData();

  formData.append("file", file);

  formData.append(
    "user_id",
    String(userId)
  );

  const token =
    localStorage.getItem("token");

  const response = await fetch(
    "http://127.0.0.1:8000/profile/upload-resume",
    {
      method: "POST",
      headers: {
        Authorization: token
          ? `Bearer ${token}`
          : "",
      },
      body: formData,
    }
  );

  if (!response.ok) {
    const error =
      await response.json();

    console.error(error);

    throw new Error(
      error.detail ||
      "Resume upload failed"
    );
  }

  return response.json();
}