import { toast } from "sonner";

export async function captureAndShare(element: HTMLElement, filename: string) {
  try {
    const { default: html2canvas } = await import("html2canvas");
    const canvas = await html2canvas(element, {
      backgroundColor: null,
      scale: 2,
      onclone: (doc) => {
        // html2canvas can't parse oklch/oklab/color-mix — replace entire
        // declaration values that reference them with transparent.
        // Keeps Tailwind structural classes (flex, rounded, etc.) intact.
        doc.querySelectorAll("style").forEach((style) => {
          style.textContent = style.textContent?.replace(
            /(:)\s*[^;{}]*(?:oklch|oklab)[^;{}]*/g,
            "$1 transparent",
          ) ?? "";
        });
      },
    });
    const blob = await new Promise<Blob>((resolve) =>
      canvas.toBlob((b) => resolve(b!), "image/png"),
    );

    // Try native share (mobile), fallback to download
    if (navigator.share && navigator.canShare?.({ files: [new File([blob], filename)] })) {
      await navigator.share({
        files: [new File([blob], filename, { type: "image/png" })],
      });
    } else {
      const url = URL.createObjectURL(blob);
      const a = document.createElement("a");
      a.href = url;
      a.download = filename;
      a.click();
      URL.revokeObjectURL(url);
      toast.success("Card saved");
    }
  } catch (err) {
    const msg = err instanceof Error ? err.message : "Unknown error";
    toast.error(`Share failed: ${msg}`);
    console.error("captureAndShare error:", err);
  }
}
