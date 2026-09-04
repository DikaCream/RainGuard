import { Link } from "react-router-dom";
import { CONTRACT_ADDRESS } from "../config";
import Logo from "./Logo";

export default function Footer() {
  return (
    <footer className="footer">
      <div className="container footer-grid">
        <div>
          <Logo />
          <p className="muted" style={{ maxWidth: 380, marginTop: 12 }}>
            RainGuard ties a payout to a published weather number. An insurer
            funds it, a buyer pays for the coverage, and when the window closes
            GenLayer's validators read the Open-Meteo archive. Hit or miss, the
            numbers settle it.
          </p>
        </div>
        <div className="footer-col">
          <strong>Explore</strong>
          <Link to="/policies">All policies</Link>
          <Link to="/create">Issue a policy</Link>
        </div>
        <div className="footer-col">
          <strong>Network</strong>
          <a href="https://genlayer.com" target="_blank" rel="noreferrer">
            GenLayer
          </a>
          <a href="https://docs.genlayer.com" target="_blank" rel="noreferrer">
            Docs
          </a>
        </div>
        <div className="footer-col">
          <strong>Contract</strong>
          {CONTRACT_ADDRESS && CONTRACT_ADDRESS !== "0x0000000000000000000000000000000000000000" ? (
            <a
              href={`https://explorer-studio.genlayer.com/address/${CONTRACT_ADDRESS}`}
              target="_blank"
              rel="noreferrer"
              className="mono"
            >
              {CONTRACT_ADDRESS.slice(0, 10)}…{CONTRACT_ADDRESS.slice(-6)}
            </a>
          ) : (
            <span className="muted">Not configured yet</span>
          )}
          <a href="https://open-meteo.com/" target="_blank" rel="noreferrer" className="muted">
            Data: Open-Meteo archive
          </a>
        </div>
      </div>
    </footer>
  );
}
