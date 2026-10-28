const corsHeaders = {
  "Access-Control-Allow-Origin": "*",
  "Access-Control-Allow-Headers": "authorization, x-client-info, apikey, content-type",
};

const IG_APP_ID = "936619743392459";

async function getUser(username: string, sessionid: string) {
  const r = await fetch(
    `https://www.instagram.com/api/v1/users/web_profile_info/?username=${username}`,
    {
      headers: {
        "x-ig-app-id": IG_APP_ID,
        "x-requested-with": "XMLHttpRequest",
        "user-agent": "Mozilla/5.0 (iPhone; CPU iPhone OS 17_0 like Mac OS X) AppleWebKit/605.1.15 (KHTML, like Gecko) Version/17.0 Mobile/15E148 Safari/604.1",
        "cookie": `sessionid=${sessionid}`,
        "referer": "https://www.instagram.com/",
        "accept": "*/*",
      },
    }
  );
  if (!r.ok) throw new Error(`IG profile error ${r.status}`);
  const data = await r.json();
  return data?.data?.user;
}

async function getFeed(userId: string, sessionid: string, count = 30) {
  const r = await fetch(
    `https://www.instagram.com/api/v1/feed/user/${userId}/?count=${count}`,
    {
      headers: {
        "x-ig-app-id": IG_APP_ID,
        "x-requested-with": "XMLHttpRequest",
        "user-agent": "Mozilla/5.0 (iPhone; CPU iPhone OS 17_0 like Mac OS X) AppleWebKit/605.1.15 (KHTML, like Gecko) Version/17.0 Mobile/15E148 Safari/604.1",
        "cookie": `sessionid=${sessionid}`,
        "referer": "https://www.instagram.com/",
        "accept": "*/*",
      },
    }
  );
  if (!r.ok) throw new Error(`IG feed error ${r.status}`);
  return r.json();
}

async function getMediaInfo(mediaId: string, sessionid: string) {
  const r = await fetch(
    `https://www.instagram.com/api/v1/media/${mediaId}/info/`,
    {
      headers: {
        "x-ig-app-id": IG_APP_ID,
        "x-requested-with": "XMLHttpRequest",
        "user-agent": "Mozilla/5.0 (iPhone; CPU iPhone OS 17_0 like Mac OS X) AppleWebKit/605.1.15 (KHTML, like Gecko) Version/17.0 Mobile/15E148 Safari/604.1",
        "cookie": `sessionid=${sessionid}`,
        "referer": "https://www.instagram.com/",
        "accept": "*/*",
      },
    }
  );
  if (!r.ok) return null;
  const data = await r.json();
  return data?.items?.[0];
}

Deno.serve(async (req) => {
  if (req.method === "OPTIONS") {
    return new Response("ok", { headers: corsHeaders });
  }

  try {
    const { username, sessionid: bodySession } = await req.json();
    if (!username) throw new Error("username is required");

    // Use session from body or from env secret
    const sessionid = (bodySession || Deno.env.get("IG_SESSION_ID") || "").trim();
    if (!sessionid) throw new Error("IG session cookie required");

    // 1. Get user profile
    const user = await getUser(username, sessionid);
    if (!user) throw new Error(`User @${username} not found`);

    // 2. Get feed
    const feed = await getFeed(user.id, sessionid, 30);
    const items = feed?.items || [];

    // 3. Map to our format + fetch video URLs for videos
    const postsRaw = items.map((p: Record<string, unknown>) => {
      const caption = p.caption as Record<string, string> | null;
      const imageVersions = p.image_versions2 as Record<string, Array<Record<string, string>>> | null;
      return {
        apify_post_id: p.code as string || String(p.pk),
        post_url: `https://www.instagram.com/p/${p.code}/`,
        thumbnail_url: imageVersions?.candidates?.[0]?.url || null,
        caption: (caption?.text || "").slice(0, 2000),
        likes: (p.like_count as number) || 0,
        views: (p.view_count as number) || (p.play_count as number) || 0,
        comments: (p.comment_count as number) || 0,
        posted_at: p.taken_at ? new Date((p.taken_at as number) * 1000).toISOString() : null,
        is_video: (p.media_type as number) === 2,
        media_id: String(p.pk),
      };
    });

    // 4. Fetch video URLs for video posts (top 5 only to avoid rate limits)
    const posts = await Promise.all(
      postsRaw.slice(0, 5).map(async (p) => {
        if (!p.is_video) return p;
        try {
          const info = await getMediaInfo(p.media_id, sessionid);
          if (info?.video_versions?.[0]?.url) {
            p.video_url = info.video_versions[0].url;
          }
        } catch (_) {
          // Silently fail — video_url stays null
        }
        return p;
      })
    ).then((topPosts) => [...topPosts, ...postsRaw.slice(5)]);

    // Sort by engagement
    posts.sort((a: Record<string, unknown>, b: Record<string, unknown>) =>
      ((b.likes as number) + (b.views as number) * 0.1 + (b.comments as number) * 2) -
      ((a.likes as number) + (a.views as number) * 0.1 + (a.comments as number) * 2)
    );

    // Clean up response (remove internal fields)
    const cleanPosts = posts.map((p: Record<string, unknown>) => {
      const { media_id, ...cleaned } = p;
      return cleaned;
    });

    return new Response(
      JSON.stringify({
        username: user.username,
        full_name: user.full_name,
        followers: user.edge_followed_by?.count,
        posts: cleanPosts,
      }),
      { headers: { ...corsHeaders, "Content-Type": "application/json" } }
    );
  } catch (err) {
    return new Response(
      JSON.stringify({ error: String(err) }),
      { status: 500, headers: { ...corsHeaders, "Content-Type": "application/json" } }
    );
  }
});
