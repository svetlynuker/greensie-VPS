import { BrowserRouter, Navigate, Route, Routes } from "react-router-dom";
import Login from "./pages/Login";
import Rozcestnik from "./pages/Rozcestnik";
import PrehledProjektu from "./pages/PrehledProjektu";
import { getToken } from "./api";

function VyzadujePrihlaseni({ children }) {
  return getToken() ? children : <Navigate to="/" replace />;
}

export default function App() {
  return (
    <BrowserRouter>
      <Routes>
        <Route path="/" element={<Login />} />
        <Route
          path="/rozcestnik"
          element={
            <VyzadujePrihlaseni>
              <Rozcestnik />
            </VyzadujePrihlaseni>
          }
        />
        <Route
          path="/projekty"
          element={
            <VyzadujePrihlaseni>
              <PrehledProjektu />
            </VyzadujePrihlaseni>
          }
        />
      </Routes>
    </BrowserRouter>
  );
}
