const API = "http://127.0.0.1:9477";

chrome.runtime.onMessage.addListener((m, _s, reply) => {
  (async () => {
    if (m.type === "start") {
      // Send logged-in YouTube cookies so yt-dlp is not blocked as a bot
      const all = [
        ...(await chrome.cookies.getAll({ domain: "youtube.com" })),
        ...(await chrome.cookies.getAll({ domain: "google.com" })),
      ];
      m.cookies = all.map((c) => ({
        domain: c.domain,
        path: c.path,
        secure: c.secure,
        expires: c.expirationDate || 0,
        name: c.name,
        value: c.value,
      }));
    }
    const r = await fetch(`${API}/${m.type}`, {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify(m),
    });
    reply({ ok: true, ...(await r.json()) });
  })().catch(() => reply({ ok: false }));
  return true;
});
