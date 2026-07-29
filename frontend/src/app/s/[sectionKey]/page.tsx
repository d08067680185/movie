import { redirect } from "next/navigation";

export default async function SectionLandingPage({
  params,
}: {
  params: Promise<{ sectionKey: string }>;
}) {
  const { sectionKey } = await params;
  redirect(`/search?section=${encodeURIComponent(sectionKey)}`);
}
