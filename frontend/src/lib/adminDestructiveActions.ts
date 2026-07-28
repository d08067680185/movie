// 管理后台三个破坏性操作(删除下载任务/批量删除资源/合并重复组)的核心逻辑，
// 从 admin/page.tsx 抽出来是为了能脱离整个2300+行组件单独写测试，
// 不是要重构整个文件——其余状态更新(setMsg/loadXxx等)仍留在调用方。

export type ApiFetchFn = (path: string, opts: RequestInit, token: string) => Promise<Response>;
export type ConfirmFn = (message: string) => boolean;

export interface ActionResult {
  cancelled: boolean;
  ok: boolean;
  message?: string;
}

export async function deleteDownloadAction(
  id: number,
  token: string,
  apiFetch: ApiFetchFn,
  confirmFn: ConfirmFn,
): Promise<ActionResult> {
  const msg = `删除下载任务 #${id}？\n如果任务还在下载中，无法真正终止底层进程，但会从列表和数据库中移除、释放已占用的部分文件空间。`;
  if (!confirmFn(msg)) return { cancelled: true, ok: false };

  const resp = await apiFetch(`/api/admin/downloads/${id}`, { method: "DELETE" }, token);
  return { cancelled: false, ok: resp.ok };
}

export async function bulkDeleteResourcesAction(
  ids: number[],
  token: string,
  apiFetch: ApiFetchFn,
  confirmFn: ConfirmFn,
): Promise<ActionResult> {
  if (ids.length === 0) return { cancelled: true, ok: false };

  const msg = `确认批量删除选中的 ${ids.length} 条资源及其所有链接？此操作不可恢复。`;
  if (!confirmFn(msg)) return { cancelled: true, ok: false };

  const resp = await apiFetch(
    "/api/admin/resources/bulk-delete",
    { method: "POST", body: JSON.stringify({ ids }) },
    token,
  );
  if (!resp.ok) return { cancelled: false, ok: false, message: "批量删除失败" };
  const d = await resp.json();
  return { cancelled: false, ok: true, message: d.message };
}

export async function mergeGroupAction(
  keepId: number,
  dupIds: number[],
  title: string,
  token: string,
  apiFetch: ApiFetchFn,
  confirmFn: ConfirmFn,
): Promise<ActionResult> {
  const msg = `一键合并「${title}」整组？\n将保留 ID:${keepId}，把其余 ${dupIds.length} 条的链接合并进来后删除。`;
  if (!confirmFn(msg)) return { cancelled: true, ok: false };

  const resp = await apiFetch(
    "/api/admin/duplicates/merge-group",
    { method: "POST", body: JSON.stringify({ keep_id: keepId, dup_ids: dupIds }) },
    token,
  );
  if (!resp.ok) return { cancelled: false, ok: false };
  const d = await resp.json();
  return { cancelled: false, ok: true, message: d.message };
}
