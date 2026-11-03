// All calls to the backend (Member 3) are kept in this one file.
// If the backend runs on a different port, change it here.
const BASE_URL = "http://localhost:8000/api";

// read the JSON answer, or throw an error with the backend's message
async function readResponse(response) {
  let data = null;
  try {
    data = await response.json();
  } catch {
    data = null;   // for example a crash page that is not JSON
  }
  if (!response.ok) {
    if (data && data.detail) {
      throw new Error(data.detail);
    }
    throw new Error("Server error " + response.status);
  }
  return data;
}

async function getData(path) {
  const response = await fetch(BASE_URL + path);
  return readResponse(response);
}

async function postData(path, body) {
  const response = await fetch(BASE_URL + path, {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify(body),
  });
  return readResponse(response);
}

async function uploadFile(file) {
  const form = new FormData();
  form.append("file", file);
  const response = await fetch(BASE_URL + "/upload", { method: "POST", body: form });
  return readResponse(response);
}

export const api = {
  dashboard: () => getData("/dashboard"),
  products: () => getData("/products"),
  reorder: () => getData("/reorder"),
  forecast: (productId) => getData("/forecast/" + productId),
  metrics: () => getData("/metrics"),
  movements: () => getData("/movements"),
  addMovement: (movement) => postData("/movements", movement),
  suppliers: () => getData("/suppliers"),
  ask: (question) => postData("/ask", { question: question }),
  documents: () => getData("/documents"),
  upload: (file) => uploadFile(file),
};
