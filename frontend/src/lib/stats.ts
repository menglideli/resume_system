/** 前端确定性统计：与后端 resume_stats 同口径（隐藏条目不计），用于编辑器实时预览与版本 diff。 */
import type { ResumeSection } from "./types";

export interface LocalStats {
  char_count: number;
  item_count: number;
  bullet_count: number;
  estimated_pages: number;
  keyword_total: number;
  keyword_covered: number;
  keyword_coverage: number | null;
  covered_keywords: string[];
  missing_keywords: string[];
}

/** 拼接所有可见文本（与后端 collect_visible_text 对齐） */
export function visibleText(data: { header?: any; sections?: ResumeSection[] } | null | undefined): string {
  const parts: string[] = [String(data?.header?.title || "")];
  for (const sec of data?.sections || []) {
    if (sec.type === "summary") { parts.push(String(sec.content || "")); continue; }
    for (const it of (sec.items || []) as any[]) {
      if (!it || it.hidden) continue;
      for (const k of ["company", "position", "period", "name", "role", "school", "major", "degree", "issuer", "category", "level"]) {
        if (typeof it[k] === "string") parts.push(it[k]);
      }
      for (const lk of ["tech_stack", "bullets"]) {
        if (Array.isArray(it[lk])) parts.push(...it[lk].map(String));
      }
    }
  }
  return parts.join("\n");
}

export function computeLocalStats(
  data: { header?: any; sections?: ResumeSection[] } | null | undefined,
  jdParsed?: { keywords?: string[]; ats_keywords?: string[] } | null,
): LocalStats {
  const text = visibleText(data);
  const char_count = text.replace(/\s/g, "").length;
  let item_count = 0;
  let bullet_count = 0;
  for (const sec of data?.sections || []) {
    if (sec.type === "summary") continue;
    for (const it of (sec.items || []) as any[]) {
      if (!it || it.hidden) continue;
      item_count++;
      if (Array.isArray(it.bullets)) bullet_count += it.bullets.length;
    }
  }
  const keywords = [...(jdParsed?.keywords || []), ...(jdParsed?.ats_keywords || [])]
    .map((k) => String(k).trim()).filter(Boolean);
  const lowered = text.toLowerCase();
  const covered = keywords.filter((k) => lowered.includes(k.toLowerCase()));
  const missing = keywords.filter((k) => !lowered.includes(k.toLowerCase()));
  return {
    char_count, item_count, bullet_count,
    estimated_pages: Math.max(1, Math.ceil(char_count / 900)),
    keyword_total: keywords.length,
    keyword_covered: covered.length,
    keyword_coverage: keywords.length ? Math.round((covered.length / keywords.length) * 100) : null,
    covered_keywords: covered,
    missing_keywords: missing,
  };
}
