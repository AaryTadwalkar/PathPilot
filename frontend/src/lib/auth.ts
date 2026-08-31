export function saveAuth(
  token: string,
  user: any
) {

  localStorage.setItem(
    "access_token",
    token
  );

  localStorage.setItem(
    "user",
    JSON.stringify(user)
  );
}

export function getToken() {
  return localStorage.getItem(
    "access_token"
  );
}

export function getUser() {

  const user =
    localStorage.getItem("user");

  return user
    ? JSON.parse(user)
    : null;
}

export function logout() {

  localStorage.removeItem(
    "access_token"
  );

  localStorage.removeItem(
    "user"
  );
}