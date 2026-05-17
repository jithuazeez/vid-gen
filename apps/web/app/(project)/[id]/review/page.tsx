"use client";
// Legacy review route — folded into the async editor. The editor now
// hosts both the in-flight rendering view and the post-render review:
// once `allDone` flips, the same screen exposes "Generate final video"
// which opens the existing export modal.
import * as React from "react";
import { useParams, useRouter } from "next/navigation";

export default function ReviewPage() {
  const { id } = useParams<{ id: string }>();
  const router = useRouter();
  React.useEffect(() => { router.replace(`/${id}/editor`); }, [id, router]);
  return null;
}
