const GOOGLE_NGRAM_URL = "https://books.google.com/ngrams/json";

const CORS_HEADERS = {
  "Access-Control-Allow-Origin": "*",
  "Access-Control-Allow-Methods": "GET, HEAD, OPTIONS",
  "Access-Control-Allow-Headers": "Content-Type",
  "Access-Control-Max-Age": "86400",
};

const ALLOWED_PARAMS = new Set([
  "content",
  "year_start",
  "year_end",
  "corpus",
  "smoothing",
  "case_insensitive",
]);

function responseWithCors(body, init = {}) {
  const headers = new Headers(init.headers || {});

  for (const [key, value] of Object.entries(CORS_HEADERS)) {
    headers.set(key, value);
  }

  return new Response(body, {
    ...init,
    headers,
  });
}

function jsonError(message, status = 400) {
  return responseWithCors(JSON.stringify({ error: message }), {
    status,
    headers: {
      "Content-Type": "application/json; charset=utf-8",
    },
  });
}

function isIntegerInRange(value, min, max) {
  if (!/^\d+$/.test(value || "")) return false;

  const number = Number(value);
  return number >= min && number <= max;
}

function isValidCorpus(value) {
  return (
    isIntegerInRange(value, 0, 999) ||
    /^[a-z][a-z0-9_]{1,31}$/.test(value || "")
  );
}

function buildGoogleUrl(requestUrl) {
  const targetUrlParam = requestUrl.searchParams.get("url");

  if (targetUrlParam) {
    const target = new URL(targetUrlParam);

    if (
      target.protocol !== "https:" ||
      target.hostname !== "books.google.com" ||
      target.pathname !== "/ngrams/json"
    ) {
      throw new Error("The url parameter must point to https://books.google.com/ngrams/json.");
    }

    return target;
  }

  const target = new URL(GOOGLE_NGRAM_URL);

  for (const [key, value] of requestUrl.searchParams.entries()) {
    if (ALLOWED_PARAMS.has(key)) {
      target.searchParams.append(key, value);
    }
  }

  return target;
}

function validateGoogleUrl(target) {
  const content = target.searchParams.get("content") || "";
  const yearStart = target.searchParams.get("year_start") || "";
  const yearEnd = target.searchParams.get("year_end") || "";
  const corpus = target.searchParams.get("corpus") || "";
  const smoothing = target.searchParams.get("smoothing") || "0";

  if (!content.trim()) {
    throw new Error("Missing required content parameter.");
  }

  if (content.length > 1200) {
    throw new Error("The content parameter is too long.");
  }

  if (!isIntegerInRange(yearStart, 1400, 2100)) {
    throw new Error("year_start must be an integer between 1400 and 2100.");
  }

  if (!isIntegerInRange(yearEnd, 1400, 2100)) {
    throw new Error("year_end must be an integer between 1400 and 2100.");
  }

  if (Number(yearStart) > Number(yearEnd)) {
    throw new Error("year_start cannot be greater than year_end.");
  }

  if (!isValidCorpus(corpus)) {
    throw new Error("corpus must be a valid Google Ngram corpus identifier.");
  }

  if (!isIntegerInRange(smoothing, 0, 50)) {
    throw new Error("smoothing must be an integer between 0 and 50.");
  }
}

export default {
  async fetch(request) {
    if (request.method === "OPTIONS") {
      return responseWithCors(null, { status: 204 });
    }

    if (!["GET", "HEAD"].includes(request.method)) {
      return jsonError("Method not allowed.", 405);
    }

    let target;

    try {
      const requestUrl = new URL(request.url);
      target = buildGoogleUrl(requestUrl);
      validateGoogleUrl(target);
    } catch (error) {
      return jsonError(error.message || String(error), 400);
    }

    const googleResponse = await fetch(target.toString(), {
      method: request.method,
    });

    const headers = new Headers(googleResponse.headers);
    headers.set("Cache-Control", "public, max-age=3600");

    return responseWithCors(googleResponse.body, {
      status: googleResponse.status,
      statusText: googleResponse.statusText,
      headers,
    });
  },
};
