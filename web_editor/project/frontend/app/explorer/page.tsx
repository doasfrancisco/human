import { redirect } from "next/navigation";

export default async function ExplorerPage({
  searchParams,
}: {
  searchParams: Promise<{ path?: string }>;
}) {
  const { path } = await searchParams;
  redirect(path ? `/?path=${encodeURIComponent(path)}` : "/");
}
