import { useEffect, useRef, useState } from "react";
import { motion } from "framer-motion";
import { ImageOff, Loader2, Trash2, Upload, ZoomIn } from "lucide-react";
import { toast } from "sonner";
import { PageHeader } from "@/components/PageHeader";
import { deletePhoto, listPhotos, photoUrl, uploadPhoto } from "@/lib/db";
import type { Photo } from "@/lib/types";
import { Button } from "@/components/ui/button";
import { Select, SelectContent, SelectItem, SelectTrigger, SelectValue } from "@/components/ui/select";
import { Dialog, DialogContent, DialogTitle } from "@/components/ui/dialog";

const CATEGORIES: { key: string; label: string; color: string }[] = [
  { key: "", label: "全部", color: "" },
  { key: "work", label: "工作", color: "bg-cyan-500/15 text-cyan-300 border-cyan-500/30" },
  { key: "life", label: "生活", color: "bg-emerald-500/15 text-emerald-300 border-emerald-500/30" },
  { key: "other", label: "其他", color: "bg-slate-500/15 text-slate-300 border-slate-500/30" },
];
const catMeta = (key: string) => CATEGORIES.find((c) => c.key === key) ?? CATEGORIES[3];

const fmtSize = (n: number | null) =>
  n == null ? "" : n > 1024 * 1024 ? `${(n / 1024 / 1024).toFixed(1)} MB` : `${Math.ceil(n / 1024)} KB`;

/** 单张照片卡片：带鉴权异步加载缩略图 */
function PhotoCard({ photo, onPreview, onDelete }: {
  photo: Photo; onPreview: (p: Photo, url: string) => void; onDelete: (p: Photo) => void;
}) {
  const [url, setUrl] = useState("");
  const [failed, setFailed] = useState(false);

  useEffect(() => {
    let alive = true;
    photoUrl(photo).then((u) => { if (alive) setUrl(u); }).catch(() => { if (alive) setFailed(true); });
    return () => { alive = false; };
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [photo.id]);

  const meta = catMeta(photo.category);
  return (
    <motion.div initial={{ opacity: 0, y: 8 }} animate={{ opacity: 1, y: 0 }}
      className="glass overflow-hidden group">
      <div className="relative aspect-[4/3] bg-white/[0.03] cursor-pointer" onClick={() => url && onPreview(photo, url)}>
        {url ? (
          <img src={url} alt={photo.original_filename} className="w-full h-full object-cover" />
        ) : (
          <div className="w-full h-full flex items-center justify-center">
            {failed ? <ImageOff className="w-6 h-6 text-slate-600" /> : <Loader2 className="w-6 h-6 animate-spin text-cyan-400/60" />}
          </div>
        )}
        {url && (
          <div className="absolute inset-0 bg-black/40 opacity-0 group-hover:opacity-100 transition-opacity flex items-center justify-center">
            <ZoomIn className="w-6 h-6 text-white" />
          </div>
        )}
      </div>
      <div className="p-3 flex items-center gap-2">
        <div className="flex-1 min-w-0">
          <div className="text-xs font-medium truncate">{photo.original_filename}</div>
          <div className="text-[10px] text-slate-500">{photo.created_at?.slice(0, 10)} · {fmtSize(photo.size)}</div>
        </div>
        <span className={`chip ${meta.color}`}>{meta.label}</span>
        <Button size="icon" variant="ghost" className="h-7 w-7 text-slate-400 hover:text-rose-300" onClick={() => onDelete(photo)}>
          <Trash2 className="w-3.5 h-3.5" />
        </Button>
      </div>
    </motion.div>
  );
}

export default function PhotosPage() {
  const [photos, setPhotos] = useState<Photo[]>([]);
  const [loading, setLoading] = useState(true);
  const [filter, setFilter] = useState("");           // "" = 全部
  const [category, setCategory] = useState("work");   // 上传时使用的分类
  const [uploading, setUploading] = useState(false);
  const [preview, setPreview] = useState<{ photo: Photo; url: string } | null>(null);
  const fileRef = useRef<HTMLInputElement>(null);

  const reload = async () => {
    setLoading(true);
    try { setPhotos(await listPhotos()); } catch (e: any) { toast.error(e.message); }
    setLoading(false);
  };

  useEffect(() => { reload(); }, []);

  const onPickFiles = async (files: FileList | null) => {
    if (!files?.length) return;
    setUploading(true);
    let ok = 0;
    for (const f of Array.from(files)) {
      try { await uploadPhoto(f, category); ok += 1; }
      catch (e: any) { toast.error(`${f.name}：${e.message}`); }
    }
    setUploading(false);
    if (fileRef.current) fileRef.current.value = "";
    if (ok) { toast.success(`已上传 ${ok} 张照片`); reload(); }
  };

  const onDelete = async (p: Photo) => {
    if (!confirm(`确认删除「${p.original_filename}」？文件与记录将一并删除。`)) return;
    try { await deletePhoto(p.id); toast.success("已删除"); reload(); }
    catch (e: any) { toast.error(e.message); }
  };

  const shown = filter ? photos.filter((p) => p.category === filter) : photos;

  return (
    <div>
      <PageHeader title="照片库" desc="存放工作照、生活照，随取随用（仅本人可见）" />

      <div className="glass p-4 mb-4 flex flex-wrap items-center gap-3">
        <div className="flex gap-1.5">
          {CATEGORIES.map((c) => (
            <button key={c.key} onClick={() => setFilter(c.key)}
              className={`px-3 py-1.5 rounded-lg text-xs transition-colors border ${
                filter === c.key
                  ? "bg-gradient-to-r from-cyan-500/25 to-violet-500/25 text-white border-cyan-500/40"
                  : "bg-white/[0.04] text-slate-400 border-transparent hover:text-white"
              }`}>
              {c.label}{c.key && ` · ${photos.filter((p) => p.category === c.key).length}`}
            </button>
          ))}
        </div>

        <div className="flex-1" />

        <Select value={category} onValueChange={setCategory}>
          <SelectTrigger className="w-32 bg-white/[0.05] border-white/10 text-sm h-9">
            <SelectValue />
          </SelectTrigger>
          <SelectContent className="bg-[#0b1120] border-white/10 text-slate-200">
            <SelectItem value="work">分类：工作</SelectItem>
            <SelectItem value="life">分类：生活</SelectItem>
            <SelectItem value="other">分类：其他</SelectItem>
          </SelectContent>
        </Select>

        <input ref={fileRef} type="file" accept="image/*" multiple className="hidden"
          onChange={(e) => onPickFiles(e.target.files)} />
        <Button className="gradient-btn" disabled={uploading} onClick={() => fileRef.current?.click()}>
          {uploading ? <Loader2 className="w-4 h-4 mr-2 animate-spin" /> : <Upload className="w-4 h-4 mr-2" />}
          上传照片
        </Button>
      </div>

      {loading ? (
        <div className="flex justify-center py-24"><Loader2 className="w-8 h-8 animate-spin text-cyan-400" /></div>
      ) : shown.length === 0 ? (
        <div className="glass p-16 text-center text-sm text-slate-500">
          暂无照片，选择分类后点击「上传照片」（支持 jpg / png / gif / webp，可多选）
        </div>
      ) : (
        <div className="grid sm:grid-cols-2 lg:grid-cols-3 xl:grid-cols-4 gap-4">
          {shown.map((p) => (
            <PhotoCard key={p.id} photo={p} onPreview={(photo, url) => setPreview({ photo, url })} onDelete={onDelete} />
          ))}
        </div>
      )}

      {/* 大图预览 */}
      <Dialog open={!!preview} onOpenChange={(o) => !o && setPreview(null)}>
        <DialogContent className="bg-[#0b1120] border-white/10 max-w-3xl p-2">
          <DialogTitle className="sr-only">照片预览</DialogTitle>
          {preview && (
            <img src={preview.url} alt={preview.photo.original_filename}
              className="w-full max-h-[80vh] object-contain rounded-lg" />
          )}
        </DialogContent>
      </Dialog>
    </div>
  );
}
