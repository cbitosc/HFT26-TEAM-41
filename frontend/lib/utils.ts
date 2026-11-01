// shadcn/ui's class-name helper: clsx for conditionals, tailwind-merge so later classes win.
import { clsx, type ClassValue } from "clsx";
import { twMerge } from "tailwind-merge";

export function cn(...inputs: ClassValue[]): string {
  return twMerge(clsx(inputs));
}
