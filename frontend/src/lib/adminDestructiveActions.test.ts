import { describe, it, expect, vi } from "vitest";
import {
  deleteDownloadAction,
  bulkDeleteResourcesAction,
  mergeGroupAction,
  type ApiFetchFn,
} from "./adminDestructiveActions";

function mockApiFetch(resp: Partial<Response> & { ok: boolean }): ApiFetchFn {
  return vi.fn().mockResolvedValue(resp as Response);
}

const TOKEN = "test-token";

describe("deleteDownloadAction", () => {
  it("does not call the API when the user declines the confirm dialog", async () => {
    const apiFetch = mockApiFetch({ ok: true });
    const confirmFn = vi.fn().mockReturnValue(false);

    const result = await deleteDownloadAction(42, TOKEN, apiFetch, confirmFn);

    expect(apiFetch).not.toHaveBeenCalled();
    expect(result).toEqual({ cancelled: true, ok: false });
  });

  it("sends a DELETE to the correct URL when confirmed", async () => {
    const apiFetch = mockApiFetch({ ok: true });
    const confirmFn = vi.fn().mockReturnValue(true);

    const result = await deleteDownloadAction(42, TOKEN, apiFetch, confirmFn);

    expect(apiFetch).toHaveBeenCalledWith(
      "/api/admin/downloads/42",
      { method: "DELETE" },
      TOKEN,
    );
    expect(result).toEqual({ cancelled: false, ok: true });
  });

  it("reports failure when the backend responds with a non-ok status", async () => {
    const apiFetch = mockApiFetch({ ok: false });
    const confirmFn = vi.fn().mockReturnValue(true);

    const result = await deleteDownloadAction(42, TOKEN, apiFetch, confirmFn);

    expect(result).toEqual({ cancelled: false, ok: false });
  });
});

describe("bulkDeleteResourcesAction", () => {
  it("does nothing when the id list is empty, without prompting", async () => {
    const apiFetch = mockApiFetch({ ok: true });
    const confirmFn = vi.fn().mockReturnValue(true);

    const result = await bulkDeleteResourcesAction([], TOKEN, apiFetch, confirmFn);

    expect(confirmFn).not.toHaveBeenCalled();
    expect(apiFetch).not.toHaveBeenCalled();
    expect(result).toEqual({ cancelled: true, ok: false });
  });

  it("does not call the API when the user declines the confirm dialog", async () => {
    const apiFetch = mockApiFetch({ ok: true });
    const confirmFn = vi.fn().mockReturnValue(false);

    const result = await bulkDeleteResourcesAction([1, 2, 3], TOKEN, apiFetch, confirmFn);

    expect(apiFetch).not.toHaveBeenCalled();
    expect(result).toEqual({ cancelled: true, ok: false });
  });

  it("posts the selected ids and returns the backend message on success", async () => {
    const apiFetch = mockApiFetch({ ok: true, json: async () => ({ message: "已删除 3 条资源" }) });
    const confirmFn = vi.fn().mockReturnValue(true);

    const result = await bulkDeleteResourcesAction([1, 2, 3], TOKEN, apiFetch, confirmFn);

    expect(apiFetch).toHaveBeenCalledWith(
      "/api/admin/resources/bulk-delete",
      { method: "POST", body: JSON.stringify({ ids: [1, 2, 3] }) },
      TOKEN,
    );
    expect(result).toEqual({ cancelled: false, ok: true, message: "已删除 3 条资源" });
  });

  it("reports failure without parsing json when the backend responds with a non-ok status", async () => {
    const apiFetch = mockApiFetch({ ok: false });
    const confirmFn = vi.fn().mockReturnValue(true);

    const result = await bulkDeleteResourcesAction([1], TOKEN, apiFetch, confirmFn);

    expect(result).toEqual({ cancelled: false, ok: false, message: "批量删除失败" });
  });
});

describe("mergeGroupAction", () => {
  it("does not call the API when the user declines the confirm dialog", async () => {
    const apiFetch = mockApiFetch({ ok: true });
    const confirmFn = vi.fn().mockReturnValue(false);

    const result = await mergeGroupAction(1, [2, 3], "阿凡达", TOKEN, apiFetch, confirmFn);

    expect(apiFetch).not.toHaveBeenCalled();
    expect(result).toEqual({ cancelled: true, ok: false });
  });

  it("posts keep_id/dup_ids and returns the backend message on success", async () => {
    const apiFetch = mockApiFetch({ ok: true, json: async () => ({ message: "已合并" }) });
    const confirmFn = vi.fn().mockReturnValue(true);

    const result = await mergeGroupAction(1, [2, 3], "阿凡达", TOKEN, apiFetch, confirmFn);

    expect(apiFetch).toHaveBeenCalledWith(
      "/api/admin/duplicates/merge-group",
      { method: "POST", body: JSON.stringify({ keep_id: 1, dup_ids: [2, 3] }) },
      TOKEN,
    );
    expect(result).toEqual({ cancelled: false, ok: true, message: "已合并" });
  });

  it("reports failure when the backend responds with a non-ok status", async () => {
    const apiFetch = mockApiFetch({ ok: false });
    const confirmFn = vi.fn().mockReturnValue(true);

    const result = await mergeGroupAction(1, [2, 3], "阿凡达", TOKEN, apiFetch, confirmFn);

    expect(result).toEqual({ cancelled: false, ok: false });
  });
});
