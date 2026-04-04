import type {
  ApprovedSymbolResponse,
  ModelEvaluationSummaryResponse,
  ModelRegistryEntryResponse,
} from "../../../api";
import { ModelGatesSection } from "../sections/ModelGatesSection";

export function ModelsPage({
  approvedSymbols,
  evaluationReports,
  modelRegistry,
}: {
  approvedSymbols: ApprovedSymbolResponse[];
  evaluationReports: ModelEvaluationSummaryResponse[];
  modelRegistry: ModelRegistryEntryResponse[];
}) {
  return (
    <>
      <div className="page-intro">
        <p className="section-note">
          This page is dedicated to inspection: registry entries, evaluation outcomes, and the
          approval gate that decides whether a symbol can reach the paper-trading lane.
        </p>
      </div>
      <div className="detail-layout">
        <ModelGatesSection
          approvedSymbols={approvedSymbols}
          evaluationReports={evaluationReports}
          modelRegistry={modelRegistry}
        />
      </div>
    </>
  );
}
