import Anthropic from "npm:@anthropic-ai/sdk@^0.27";

const corsHeaders = {
  "Access-Control-Allow-Origin": "*",
  "Access-Control-Allow-Headers": "authorization, x-client-info, apikey, content-type",
};

Deno.serve(async (req) => {
  if (req.method === "OPTIONS") {
    return new Response("ok", { headers: corsHeaders });
  }

  try {
    const body = await req.json();

    // Config mode: return Apify token to authenticated browser
    if (body.action === "get_config") {
      return new Response(
        JSON.stringify({ apify_token: Deno.env.get("APIFY_API_TOKEN") }),
        { headers: { ...corsHeaders, "Content-Type": "application/json" } }
      );
    }

    const { dna, viral_caption, surgery_type } = body;

    const anthropic = new Anthropic({ apiKey: Deno.env.get("ANTHROPIC_API_KEY") });

    // DNA extraction mode: viral_caption IS the raw prompt
    const isDNAMode = surgery_type === "__DNA_EXTRACTION__";

    let prompt: string;

    if (isDNAMode) {
      prompt = viral_caption;
    } else {
      const dnaText = dna
        ? `TONO: ${dna.tone || "profesional y cercano"}
PALABRAS CLAVE: ${(dna.keywords || []).join(", ")}
MENSAJES CLAVE: ${(dna.key_messages || []).join(" | ")}
ESTILO: ${dna.style_notes || "educativo, natural, auténtico"}`
        : "Cirujano estético facial colombiano, tono profesional y cercano, explica procedimientos con claridad.";

      prompt = `Eres el asistente de contenido del Dr. John Bareño, cirujano estético facial de Colombia especializado en rejuvenecimiento facial.

ADN DEL DR. BAREÑO:
${dnaText}

VIDEO VIRAL DE REFERENCIA (caption del competidor):
${viral_caption || "(sin referencia — crea contenido original)"}

TIPO DE CIRUGÍA A DESTACAR: ${surgery_type}

TAREA: Crea un guión de video corto (60-90 segundos) para Instagram Reels que:
1. Se inspire en el GANCHO y estructura del video viral de referencia
2. Esté completamente adaptado al tono, estilo y ADN del Dr. Bareño
3. Hable específicamente sobre ${surgery_type}
4. Sea educativo, natural y auténtico al estilo del doctor
5. Incluya las secciones marcadas

FORMATO DE SALIDA (usa exactamente estos encabezados):

---GANCHO (0-5 seg)---
[texto del gancho — lo que atrapa al espectador en los primeros 3 segundos]

---DESARROLLO (5-50 seg)---
[explicación del procedimiento en el estilo del doctor — educativo, con detalles que generan confianza]

---CTA (50-60 seg)---
[llamado a la acción — consulta, DM, link en bio]`;
    }

    const message = await anthropic.messages.create({
      model: "claude-sonnet-4-6",
      max_tokens: 1500,
      messages: [{ role: "user", content: prompt }],
    });

    const script = (message.content[0] as { type: string; text: string }).text;

    return new Response(
      JSON.stringify({ script }),
      { headers: { ...corsHeaders, "Content-Type": "application/json" } }
    );
  } catch (err) {
    return new Response(
      JSON.stringify({ error: String(err) }),
      { status: 500, headers: { ...corsHeaders, "Content-Type": "application/json" } }
    );
  }
});
