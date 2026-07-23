import { BrowserRouter, Navigate, Route, Routes } from "react-router-dom";
import Login from "./pages/Login";
import Rozcestnik from "./pages/Rozcestnik";
import PrehledProjektu from "./pages/PrehledProjektu";
import PrehledFinanci from "./pages/PrehledFinanci";
import PrehledZmen from "./pages/PrehledZmen";
import Nabidkovac from "./pages/Nabidkovac";
import NabidkovacSekce from "./pages/NabidkovacSekce";
import NabidkaDetail from "./pages/NabidkaDetail";
import NabidkaVystupStranka from "./pages/NabidkaVystupStranka";
import NabidkovacKatalog from "./pages/NabidkovacKatalog";
import AdminNastaveni from "./pages/AdminNastaveni";
import Logy from "./pages/Logy";
import Konektor from "./pages/Konektor";
import ZmenaHesla from "./pages/ZmenaHesla";
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
          path="/zmena-hesla"
          element={
            <VyzadujePrihlaseni>
              <ZmenaHesla />
            </VyzadujePrihlaseni>
          }
        />
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
        <Route
          path="/finance"
          element={
            <VyzadujePrihlaseni>
              <PrehledFinanci />
            </VyzadujePrihlaseni>
          }
        />
        <Route
          path="/zmeny"
          element={
            <VyzadujePrihlaseni>
              <PrehledZmen />
            </VyzadujePrihlaseni>
          }
        />
        <Route
          path="/nabidkovac"
          element={
            <VyzadujePrihlaseni>
              <Nabidkovac />
            </VyzadujePrihlaseni>
          }
        />
        <Route
          path="/nabidkovac/katalog"
          element={
            <VyzadujePrihlaseni>
              <NabidkovacKatalog />
            </VyzadujePrihlaseni>
          }
        />
        <Route
          path="/nabidkovac/nabidka/:id"
          element={
            <VyzadujePrihlaseni>
              <NabidkaDetail />
            </VyzadujePrihlaseni>
          }
        />
        <Route
          path="/nabidkovac/nabidka/:id/vystup/:typ"
          element={
            <VyzadujePrihlaseni>
              <NabidkaVystupStranka />
            </VyzadujePrihlaseni>
          }
        />
        <Route
          path="/nabidkovac/:typ"
          element={
            <VyzadujePrihlaseni>
              <NabidkovacSekce />
            </VyzadujePrihlaseni>
          }
        />
        <Route
          path="/admin"
          element={
            <VyzadujePrihlaseni>
              <AdminNastaveni />
            </VyzadujePrihlaseni>
          }
        />
        <Route
          path="/logy"
          element={
            <VyzadujePrihlaseni>
              <Logy />
            </VyzadujePrihlaseni>
          }
        />
        <Route
          path="/konektor"
          element={
            <VyzadujePrihlaseni>
              <Konektor />
            </VyzadujePrihlaseni>
          }
        />
      </Routes>
    </BrowserRouter>
  );
}
