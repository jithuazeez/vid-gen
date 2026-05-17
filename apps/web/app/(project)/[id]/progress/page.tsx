"use client";
// Legacy progress route — superseded by the async editor. The editor
// streams per-asset state into a live timeline (scenes/voice/subs),
// which is strictly a superset of what this page used to show. We
// preserve the URL so existing deep-links keep working and redirect
// to /editor, forwarding ?job= so the editor subscribes to the same SSE.
import * as React from "react";
import { useParams, useRouter, useSearchParams } from "next/navigation";

export default function ProgressPage() {
  const { id } = useParams<{ id: string }>();
  const router = useRouter();
  const search = useSearchParams();
  const job = search.get("job");

  React.useEffect(() => {
    const qs = job ? `?job=${job}` : "";
    router.replace(`/${id}/editor${qs}`);
  }, [id, job, router]);

  return null;
}
