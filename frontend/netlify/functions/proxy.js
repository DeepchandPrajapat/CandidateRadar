exports.handler = async (event) => {

    // only allow POST requests
    if (event.httpMethod !== "POST") {
        return {
            statusCode: 405,
            body: JSON.stringify({ error: "Method not allowed" })
        };
    }

    try {
        const API_BASE = process.env.API_BASE;
        const API_KEY  = process.env.API_KEY;

        // forward the request to Render with the secret API key
        const response = await fetch(`${API_BASE}/resume/upload`, {
            method : "POST",
            headers: {
                "x-api-key"    : API_KEY,
                "content-type" : event.headers["content-type"] || event.headers["Content-Type"],
            },
            body: Buffer.from(event.body, event.isBase64Encoded ? "base64" : "utf8")
        });

        const data = await response.json();

        return {
            statusCode: response.status,
            headers   : { "Content-Type": "application/json" },
            body      : JSON.stringify(data)
        };

    } catch (err) {
        return {
            statusCode: 500,
            body      : JSON.stringify({ error: err.message })
        };
    }
};