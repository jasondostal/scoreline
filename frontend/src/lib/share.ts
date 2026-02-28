export async function captureAndShare(element: HTMLElement, filename: string) {
  const { default: html2canvas } = await import("html2canvas");
  const canvas = await html2canvas(element, {
    backgroundColor: null,
    scale: 2,
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
  }
}
