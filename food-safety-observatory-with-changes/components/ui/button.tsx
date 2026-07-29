import { Slot } from "@radix-ui/react-slot";
import { cva, type VariantProps } from "class-variance-authority";
import type { ButtonHTMLAttributes } from "react";

import { cn } from "@/lib/utils";

const buttonVariants = cva("focus-ring inline-flex min-h-11 items-center justify-center gap-2 rounded-[4px] px-4 text-sm font-semibold transition-colors disabled:pointer-events-none disabled:opacity-50", {
  variants: {
    variant: {
      primary: "bg-[var(--maroon)] text-white hover:bg-[var(--maroon-dark)]",
      secondary: "border border-[var(--maroon)] text-[var(--maroon)] hover:bg-[var(--paper-deep)]",
      ghost: "text-[var(--ink)] hover:bg-[var(--paper-deep)]",
    },
    size: { default: "h-11", sm: "h-9 min-h-9 px-3", icon: "h-10 min-h-10 w-10 p-0" },
  },
  defaultVariants: { variant: "primary", size: "default" },
});

interface ButtonProps extends ButtonHTMLAttributes<HTMLButtonElement>, VariantProps<typeof buttonVariants> { asChild?: boolean }

export function Button({ asChild, className, variant, size, ...props }: ButtonProps) {
  const Component = asChild ? Slot : "button";
  return <Component className={cn(buttonVariants({ variant, size }), className)} {...props} />;
}

export { buttonVariants };
