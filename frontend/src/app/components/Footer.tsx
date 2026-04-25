import { NOMZ_THEME } from '../constants';

const T = NOMZ_THEME;

export function Footer() {
  return (
    <footer
      className="shrink-0 flex items-center justify-between px-8 py-5 text-sm"
      style={{
        borderTop: `2px solid ${T.ink}`,
        background: T.paper,
        fontFamily: T.fontSans,
      }}
    >
      <span style={{ fontFamily: T.fontSerif, fontStyle: 'italic', fontSize: 13, color: T.tan }}>
        Good food, always.
      </span>
      <span style={{ fontSize: 10, letterSpacing: '0.3em', textTransform: 'uppercase', color: T.mid }}>
        nomz · eat. explore. repeat
      </span>
    </footer>
  );
}
