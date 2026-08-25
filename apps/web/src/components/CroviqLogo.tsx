import React from "react";

interface CroviqLogoProps {
  className?: string;
  height?: number | string;
}

export const CroviqLogo: React.FC<CroviqLogoProps> = ({
  className = "h-7 w-auto",
  height = 28,
}) => {
  return (
    <svg
      xmlns="http://www.w3.org/2000/svg"
      viewBox="0 0 1800 520"
      height={height}
      className={className}
      role="img"
      aria-label="Croviq"
    >
      <g transform="translate(0,46) scale(.51)">
        <defs>
          <clipPath id="croviq-logo-cclip">
            <polygon points="120,260 500,40 860,250 700,430 560,330 390,260 260,440 290,620 470,710 600,620 840,590 560,850 290,770 100,520" />
          </clipPath>
        </defs>
        <g clipPath="url(#croviq-logo-cclip)">
          <polygon points="100,260 500,40 390,260" fill="#FF9F1C" />
          <polygon points="100,260 390,260 260,440" fill="#FFBD16" />
          <polygon points="100,260 260,440 100,520" fill="#FFB514" />
          <polygon points="500,40 620,260 390,260" fill="#FF6B3D" />
          <polygon points="500,40 860,250 620,260" fill="#F51B35" />
          <polygon points="620,260 860,250 700,430" fill="#F52B49" />
          <polygon points="390,260 620,260 560,330" fill="#FF7A43" />
          <polygon points="260,440 390,260 330,520" fill="#FFD05A" />
          <polygon points="100,520 260,440 330,520" fill="#20A7D8" />
          <polygon points="100,520 330,520 290,620" fill="#18AEEA" />
          <polygon points="290,620 330,520 470,710" fill="#078ED8" />
          <polygon points="330,520 560,330 600,620" fill="#4B72D0" />
          <polygon points="330,520 600,620 470,710" fill="#2355C5" />
          <polygon points="600,620 840,590 560,850" fill="#6C2BBF" />
          <polygon points="600,620 700,430 840,590" fill="#B527B7" />
          <polygon points="470,710 600,620 560,850" fill="#1452C5" />
          <polygon points="290,620 470,710 560,850" fill="#0798DE" />
          <polygon points="100,520 290,620 290,770" fill="#14A9DF" />
          <polygon points="290,620 560,850 290,770" fill="#0D86D1" />
        </g>
      </g>
      <text
        x="470"
        y="405"
        fontFamily="Inter, -apple-system, BlinkMacSystemFont, 'Segoe UI', Roboto, sans-serif"
        fontSize="390"
        fontWeight="800"
        fill="#F2F4F5"
        letterSpacing="-20"
      >
        roviq
      </text>
    </svg>
  );
};
