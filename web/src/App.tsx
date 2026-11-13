import { BrowserRouter, Navigate, Route, Routes } from "react-router-dom";
import Daily from "./pages/Daily";
import Home from "./pages/Home";
import Play from "./pages/Play";
import Result from "./pages/Result";
import Setup from "./pages/Setup";
import Stats from "./pages/Stats";
import "./store/settings";

export default function App() {
  return (
    <BrowserRouter>
      <Routes>
        <Route path="/" element={<Home />} />
        <Route path="/setup/:mode" element={<Setup />} />
        <Route path="/play/:sid" element={<Play />} />
        <Route path="/result/:sid" element={<Result />} />
        <Route path="/daily" element={<Daily />} />
        <Route path="/stats" element={<Stats />} />
        <Route path="*" element={<Navigate to="/" replace />} />
      </Routes>
    </BrowserRouter>
  );
}
