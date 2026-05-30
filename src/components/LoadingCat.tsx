export default function LoadingCat() {
  return (
    <div className="flex items-center gap-3 mb-3 px-1">
      <style>{`
        @keyframes cat-hunt {
          0%, 100% { transform: translateY(0px) scale(1);    opacity: 0.9; }
          40%       { transform: translateY(-6px) scale(1.05); opacity: 1; }
          60%       { transform: translateY(-6px) scale(1.05); opacity: 1; }
          80%       { transform: translateY(0px) scale(1);    opacity: 0.9; }
        }
        @keyframes eye-glow {
          0%, 100% { opacity: 0.6; }
          50%       { opacity: 1; }
        }
        .cat-head-loader {
          animation: cat-hunt 1.4s ease-in-out infinite;
        }
        .cat-eye-glow {
          animation: eye-glow 1.4s ease-in-out infinite;
        }
      `}</style>

      <div className="cat-head-loader">
        <img
          src="/cat-head.svg"
          alt="Yara"
          style={{ height: "32px", width: "auto" }}
        />
      </div>

      <span
        className="text-sm text-[#d4f53c] font-medium"
        style={{ fontFamily: "'Barlow Condensed', sans-serif" }}
      >
        Yara ist auf der Jagd…
      </span>
    </div>
  )
}
