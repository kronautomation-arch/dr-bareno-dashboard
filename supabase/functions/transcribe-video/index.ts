const corsHeaders = {
  "Access-Control-Allow-Origin": "*",
  "Access-Control-Allow-Headers": "authorization, x-client-info, apikey, content-type",
};

Deno.serve(async (req) => {
  if (req.method === "OPTIONS") return new Response("ok", { headers: corsHeaders });

  try {
    const { video_url, sessionid: bodySession } = await req.json();
    if (!video_url) throw new Error("video_url is required");

    const rawSession = bodySession || Deno.env.get("IG_SESSION_ID") || "";
    let session = rawSession.trim();
    if (session.startsWith("sessionid=")) session = session.slice(10);
    try { session = decodeURIComponent(session); } catch (_) {}

    // Download video from Instagram CDN
    const videoRes = await fetch(video_url, {
      headers: session
        ? { "cookie": `sessionid=${session}`, "user-agent": "Mozilla/5.0 (iPhone; CPU iPhone OS 17_0 like Mac OS X) AppleWebKit/605.1.15" }
        : { "user-agent": "Mozilla/5.0" },
    });

    if (!videoRes.ok) throw new Error(`Video download failed: ${videoRes.status}`);

    const videoBuffer = await videoRes.arrayBuffer();
    const sizeMB = videoBuffer.byteLength / (1024 * 1024);

    if (sizeMB > 24) throw new Error(`Video too large (${sizeMB.toFixed(1)}MB). Max 24MB para Whisper.`);

    // Detect content type
    const contentType = videoRes.headers.get("content-type") || "video/mp4";
    const ext = contentType.includes("webm") ? "webm" : contentType.includes("mov") ? "mov" : "mp4";

    // Send to OpenAI Whisper
    const OPENAI_KEY = Deno.env.get("OPENAI_API_KEY");
    if (!OPENAI_KEY) throw new Error("OPENAI_API_KEY not configured");

    const formData = new FormData();
    formData.append("file", new Blob([videoBuffer], { type: contentType }), `video.${ext}`);
    formData.append("model", "whisper-1");
    formData.append("language", "es");
    formData.append("response_format", "text");

    const whisperRes = await fetch("https://api.openai.com/v1/audio/transcriptions", {
      method: "POST",
      headers: { "Authorization": `Bearer ${OPENAI_KEY}` },
      body: formData,
    });

    if (!whisperRes.ok) {
      const err = await whisperRes.text();
      throw new Error(`Whisper error ${whisperRes.status}: ${err.slice(0, 200)}`);
    }

    const transcription = await whisperRes.text();

    return new Response(
      JSON.stringify({ transcription: transcription.trim(), size_mb: sizeMB.toFixed(1) }),
      { headers: { ...corsHeaders, "Content-Type": "application/json" } }
    );
  } catch (err) {
    return new Response(
      JSON.stringify({ error: String(err) }),
      { status: 500, headers: { ...corsHeaders, "Content-Type": "application/json" } }
    );
  }
});
