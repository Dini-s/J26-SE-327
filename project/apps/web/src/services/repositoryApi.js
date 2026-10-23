
const API_BASE_URL = "http://127.0.0.1:8000/api/repositories";

async function request(url, options = {}) {
    const response = await fetch(url, {
        ...options,
        headers: {
            "Content-Type": "application/json",
            ...options.headers,
        },
    });

    const data = await response.json().catch(() => ({}));

    if (!response.ok) {
        throw new Error(
            data.detail || `Request failed with status ${response.status}`
        );
    }

    return data;
}

export function getRepositories() {
    return request(API_BASE_URL);
}

export function analyzeRepository(repositoryId) {
    return request(
        `${API_BASE_URL}/${encodeURIComponent(repositoryId)}/analyze`,
        { method: "POST" }
    );
}

export function registerRepository(repository) {
    return request(API_BASE_URL, {
        method: "POST",
        body: JSON.stringify(repository),
    });
}

export function cloneRepository(repositoryId) {
    return request(
        `${API_BASE_URL}/${encodeURIComponent(repositoryId)}/clone`,
        { method: "POST" }
    );
}
