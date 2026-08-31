import { apiRequest } from "@/lib/api";

export async function signup(email: string, password: string) {
  return apiRequest("/auth/signup", {
    method: "POST",
    body: JSON.stringify({
      email,
      password,
    }),
  });
}

export async function verifyOtp(
  email: string,
  otp_code: string
) {
  return apiRequest("/auth/verify-otp", {
    method: "POST",
    body: JSON.stringify({
      email,
      otp_code,
    }),
  });
}

export async function login(
  email: string,
  password: string
) {
  return apiRequest<{
    access_token: string;
    token_type: string;
  }>("/auth/login", {
    method: "POST",
    body: JSON.stringify({
      email,
      password,
    }),
  });
}