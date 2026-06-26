/** @type {import('tailwindcss').Config} */
export default {
  content: ["./index.html", "./src/**/*.{ts,tsx}"],
  theme: {
    extend: {
      colors: {
        // 정무상황판 컬러 팔레트
        navy: { DEFAULT: "#173B63", dark: "#0F2744", light: "#1E4A7A" },
        brand: { DEFAULT: "#005BAC", dark: "#003E7E" },   // 민주당 블루 (활성 메뉴·포인트)
        "purple-accent": "#6D5DF6",
        "green-accent": "#00A86B",
        "warning-orange": "#FF8A00",   // 주의·경고 전용
        "danger-red": "#E53935",       // 위기·긴급 전용
        grade: { red: "#E53935", orange: "#FF8A00", yellow: "#e6a817" },
      },
      borderColor: {
        "grade-red":    "#E53935",
        "grade-orange": "#FF8A00",
        "grade-yellow": "#e6a817",
      },
      backgroundColor: {
        page: "#F4F6F8",
      },
    },
  },
  plugins: [],
};
