// All calls to the backend (Member 3) are kept in this one file.
// If the backend runs on a different port, change it here.
const BASE_URL = "http://localhost:8000/api";

async function getData(path) {
  const response = await fetch(BASE_URL + path);
  const data = await response.json();
  if (!response.ok) {
    throw new Error(data.detail);
  }
  return data;
}

async function postData(path, body) {
  const response = await fetch(BASE_URL + path, {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify(body),
  });
  const data = await response.json();
  if (!response.ok) {
    throw new Error(data.detail);
  }
  return data;
}

async function uploadFile(file) {
  const form = new FormData();
  form.append("file", file);
  const response = await fetch(BASE_URL + "/upload", { method: "POST", body: form });
  const data = await response.json();
  if (!response.ok) {
    throw new Error(data.detail);
  }
  return data;
}

export const api = {
  dashboard: () => getData("/dashboard"),
  products: () => getData("/products"),
  reorder: () => getData("/reorder"),
  forecast: (productId) => getData("/forecast/" + productId),
  metrics: () => getData("/metrics"),
  movements: () => getData("/movements"),
  addMovement: (movement) => postData("/movements", movement),
  ask: (question) => postData("/ask", { question: question }),
  documents: () => getData("/documents"),
  upload: (file) => uploadFile(file),
};
