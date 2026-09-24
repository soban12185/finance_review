import { Route, Routes } from "react-router-dom";
import Layout from "./components/Layout";
import AnalystPage from "./pages/AnalystPage";
import ArchitecturePage from "./pages/ArchitecturePage";
import DashboardPage from "./pages/DashboardPage";
import PnLPage from "./pages/PnLPage";
import ReviewQueuePage from "./pages/ReviewQueuePage";
import TransactionsPage from "./pages/TransactionsPage";
import VariancePage from "./pages/VariancePage";

export default function App() {
  return (
    <Routes>
      <Route element={<Layout />}>
        <Route path="/" element={<DashboardPage />} />
        <Route path="/how-it-works" element={<ArchitecturePage />} />
        <Route path="/transactions" element={<TransactionsPage />} />
        <Route path="/review-queue" element={<ReviewQueuePage />} />
        <Route path="/pnl" element={<PnLPage />} />
        <Route path="/variance" element={<VariancePage />} />
        <Route path="/analyst" element={<AnalystPage />} />
      </Route>
    </Routes>
  );
}