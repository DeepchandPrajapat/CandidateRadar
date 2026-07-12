exports.config = {
  timeout: 60
};

exports.handler = async (event) => {

    if (event.httpMethod !== "POST") {
        return {
            statusCode: 405,
            body: JSON.stringify({ error: "Method not allowed" })
        };
    }

    try {
        const API_BASE = process.env.API_BASE;
        const API_KEY  = process.env.API_KEY;

        const response = await fetch(`${API_BASE}/resume/upload`, {
            method : "POST",
            headers: {
                "x-api-key"    : API_KEY,
                "content-type" : event.headers["content-type"] || event.headers["Content-Type"],
            },
            body: Buffer.from(event.body, event.isBase64Encoded ? "base64" : "utf8")
        });

        const responseText = await response.text();
        console.log("Render status:", response.status);
        console.log("Render body:", responseText.substring(0, 200));

        try {
            const data = JSON.parse(responseText);
            return {
                statusCode: response.status,
                headers   : { "Content-Type": "application/json" },
                body      : JSON.stringify(data)
            };
        } catch {
            return {
                statusCode: 500,
                headers   : { "Content-Type": "application/json" },
                body      : JSON.stringify({ error: "Render returned non-JSON", raw: responseText.substring(0, 200) })
            };
        }

    } catch (err) {
        return {
            statusCode: 500,
            body      : JSON.stringify({ error: err.message })
        };
    }
};