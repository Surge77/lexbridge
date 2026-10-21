import JsBarcode from "jsbarcode";
import { useEffect, useRef } from "react";

interface BarcodeProps {
  value: string;
}

// A real, scannable Code 128 of the answer's trace id: the reference to quote when
// reporting a wrong answer.
export function Barcode({ value }: BarcodeProps) {
  const svg = useRef<SVGSVGElement>(null);

  useEffect(() => {
    if (!svg.current) return;
    try {
      JsBarcode(svg.current, value, { format: "CODE128", displayValue: false, margin: 0, height: 56, width: 1.3, lineColor: "#222222", background: "transparent" });
    } catch {
      svg.current.replaceChildren();
    }
  }, [value]);

  return <svg ref={svg} className="barcode" role="img" aria-label={`Barcode of trace ${value}`} />;
}
