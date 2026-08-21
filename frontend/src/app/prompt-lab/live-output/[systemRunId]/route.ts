import { loadReverieLiveRunOutput } from "@/lib/reverie-evidence";

export async function GET(_request: Request, { params }: { params: Promise<{ systemRunId: string }> }) {
  const { systemRunId } = await params;
  const evidence = await loadReverieLiveRunOutput(systemRunId);
  if (!evidence) {
    return Response.json({ error_code: "REVERIE_LIVE_RUN_NOT_AVAILABLE" }, { status: 404 });
  }
  const safeName = systemRunId.replaceAll(/[^a-zA-Z0-9_-]/g, "-");
  return new Response(evidence.output, {
    headers: {
      "Cache-Control": "public, max-age=31536000, immutable",
      "Content-Disposition": `attachment; filename="threadline-live-${safeName}.json"`,
      "Content-Type": "application/json; charset=utf-8",
      "X-THREADLINE-SHA256": evidence.sha256,
    },
  });
}
