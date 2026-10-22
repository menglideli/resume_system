import { motion } from "framer-motion";
import type { ReactNode } from "react";

export function PageHeader({ title, desc, actions }: { title: string; desc?: string; actions?: ReactNode }) {
  return (
    <motion.div
      initial={{ opacity: 0, y: -12 }}
      animate={{ opacity: 1, y: 0 }}
      transition={{ duration: 0.4 }}
      className="flex items-end justify-between mb-7"
    >
      <div>
        <h1 className="text-2xl font-bold gradient-text">{title}</h1>
        {desc && <p className="text-sm text-slate-500 mt-1">{desc}</p>}
      </div>
      {actions && <div className="flex items-center gap-3">{actions}</div>}
    </motion.div>
  );
}
