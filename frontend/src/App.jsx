import { Suspense, lazy } from "react";
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
import Zakaznici from "./pages/Zakaznici";
import ZakaznikDetail from "./pages/ZakaznikDetail";
import ObchodniPripady from "./pages/ObchodniPripady";
import Nabidky from "./pages/Nabidky";
import Objednavky from "./pages/Objednavky";
import Projekty from "./pages/Projekty";
import ProjektDetail from "./pages/ProjektDetail";
import ObchodniPripadDetail from "./pages/ObchodniPripadDetail";
import AdminNastaveni from "./pages/AdminNastaveni";
import Logy from "./pages/Logy";
import Konektor from "./pages/Konektor";
import Manual from "./pages/Manual";
import ZmenaHesla from "./pages/ZmenaHesla";
import Nastaveni from "./pages/Nastaveni";
import Kalendar from "./pages/Kalendar";
import PrehledObchodu from "./pages/PrehledObchodu";
import MujDen from "./pages/MujDen";

// Mapa se načítá až při otevření (CRM-20). Leaflet váží ~180 kB a používá ho
// jediná obrazovka — v hlavním balíku by zpomaloval start všem ostatním.
const Mapa = lazy(() => import("./pages/Mapa"));
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
          path="/muj-den"
          element={
            <VyzadujePrihlaseni>
              <MujDen />
            </VyzadujePrihlaseni>
          }
        />
        <Route
          path="/mapa"
          element={
            <VyzadujePrihlaseni>
              <Suspense fallback={null}>
                <Mapa />
              </Suspense>
            </VyzadujePrihlaseni>
          }
        />
        <Route
          path="/prehled-obchodu"
          element={
            <VyzadujePrihlaseni>
              <PrehledObchodu />
            </VyzadujePrihlaseni>
          }
        />
        <Route
          path="/kalendar"
          element={
            <VyzadujePrihlaseni>
              <Kalendar />
            </VyzadujePrihlaseni>
          }
        />
        {/* Osobní nastavení – nepotřebuje právo, každý spravuje svoje volby. */}
        <Route
          path="/nastaveni"
          element={
            <VyzadujePrihlaseni>
              <Nastaveni />
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
        {/* CRM: Zákazníci → Obchodní případy. Detaily mají v cestě „detail",
            aby se nepletly s pohledy (/zakaznici/lead vs. /zakaznici/detail/7). */}
        <Route
          path="/zakaznici"
          element={<Navigate to="/zakaznici/lead" replace />}
        />
        <Route
          path="/zakaznici/detail/:id"
          element={
            <VyzadujePrihlaseni>
              <ZakaznikDetail />
            </VyzadujePrihlaseni>
          }
        />
        <Route
          path="/zakaznici/:pohled"
          element={
            <VyzadujePrihlaseni>
              <Zakaznici />
            </VyzadujePrihlaseni>
          }
        />
        <Route
          path="/nabidky"
          element={
            <VyzadujePrihlaseni>
              <Nabidky />
            </VyzadujePrihlaseni>
          }
        />
        <Route
          path="/pripady"
          element={
            <VyzadujePrihlaseni>
              <ObchodniPripady />
            </VyzadujePrihlaseni>
          }
        />
        <Route
          path="/pripady/detail/:id"
          element={
            <VyzadujePrihlaseni>
              <ObchodniPripadDetail />
            </VyzadujePrihlaseni>
          }
        />
        <Route
          path="/objednavky"
          element={
            <VyzadujePrihlaseni>
              <Objednavky />
            </VyzadujePrihlaseni>
          }
        />
        {/* CRM projekty žijí na /projekty; starý Přehled projektů (matice
            z Freela) zůstává na /prehled-projektu, dokud ho appka nenahradí. */}
        <Route
          path="/projekty"
          element={
            <VyzadujePrihlaseni>
              <Projekty />
            </VyzadujePrihlaseni>
          }
        />
        <Route
          path="/projekty/detail/:id"
          element={
            <VyzadujePrihlaseni>
              <ProjektDetail />
            </VyzadujePrihlaseni>
          }
        />
        <Route
          path="/prehled-projektu"
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
        <Route
          path="/manual"
          element={
            <VyzadujePrihlaseni>
              <Manual />
            </VyzadujePrihlaseni>
          }
        />
      </Routes>
    </BrowserRouter>
  );
}
