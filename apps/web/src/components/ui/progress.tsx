import * as React from "react"
import { cn } from "@/lib/utils"

// Since we didn't install radix-ui, implementing a simple CSS/div based progress for now
// to avoid extra dependency issues unless requested.
// Actually, using framer-motion for smooth animation as planned.

import { motion } from "framer-motion"

interface ProgressProps extends React.HTMLAttributes<HTMLDivElement> {
  value?: number
  max?: number
  indicatorClassName?: string
}

const Progress = React.forwardRef<HTMLDivElement, ProgressProps>(
  ({ className, value = 0, max = 100, indicatorClassName, ...props }, ref) => {
    const percentage = Math.min(Math.max(value || 0, 0), max) / max * 100

    return (
      <div
        ref={ref}
        className={cn(
          "relative h-2 w-full overflow-hidden rounded-full bg-secondary/20",
          className
        )}
        {...props}
      >
        <motion.div
          className={cn("h-full w-full flex-1 bg-primary transition-all", indicatorClassName)}
          initial={{ width: 0 }}
          animate={{ width: `${percentage}%` }}
          transition={{ duration: 0.8, ease: "easeOut" }}
        />
      </div>
    )
  }
)
Progress.displayName = "Progress"

export { Progress }
