/** @type {import('tailwindcss').Config} */
export default {
  content: ["./index.html", "./src/**/*.{ts,tsx}"],
  theme: {
    extend: {
      colors: {
        // PDF 대시보드 톤: 네이비 헤더 + 오렌지 포인트
        navy: { DEFAULT: "#1f3a5f", dark: "#16294a", light: "#2b4a73" },
        brand: { DEFAULT: "#f2710d", dark: "#d9620a" },
        grade: { red: "#e03131", orange: "#f08c00", yellow: "#f5c518" },
      },
      borderColor: {
        "grade-red": "#e03131",
        "grade-orange": "#f08c00",
        "grade-yellow": "#f5c518",
      },
    },
  },
  plugins: [],
};
