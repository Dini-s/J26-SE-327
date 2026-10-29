import { useEffect, useState } from "react";
import { useLocation } from "react-router-dom";
import OverviewPage from "../../pages/OverviewPage";
import RequirementsPage from "../../pages/RequirementsPage";
import RequirementDetailsPage from "../../pages/RequirementDetailsPage";
import ReportsAnalyticsPage from "../../pages/ReportsAnalyticsPage";
import { qualityApi } from "../../services/qualityApi";
function QualityApp() {
    const path = useLocation().pathname;
    const [loading, setLoading] = useState(true);
    const [error, setError] = useState(null);
    useEffect(() => {
        const initialize = async () => {
            setLoading(true);
            setError(null);
            try {
                await qualityApi.bootstrap();
            }
            catch (exception) {
                const message = exception instanceof Error
                    ? exception.message
                    : "Unable to connect " + "to the C3 API.";
                setError(message);
            }
            finally {
                setLoading(false);
            }
        };
        void initialize();
    }, []);
    if (loading) {
        return (<div className="startup-screen">
        <div className="startup-card">
          <div className="startup-logo">ASPIRE</div>

          <h1>Preparing Quality & Testing Intelligence</h1>

          <p>
            Loading requirements, RVUs, validation evidence and generated
            intelligence.
          </p>

          <div className="startup-spinner"/>
        </div>
      </div>);
    }
    if (error) {
        return (<div className="startup-screen">
        <div className="startup-card error-card">
          <div className="startup-logo">ASPIRE</div>

          <h1>Backend connection unavailable</h1>

          <p>
            The interface is ready, but the Quality Intelligence API could not
            be reached.
          </p>

          <pre className="startup-error">{error}</pre>

          <div className="startup-command">
            Start the API from the project directory:
            <br />
            <strong>python -m uvicorn apps.api.main:app --reload</strong>
          </div>

          <button className="primary-button" onClick={() => window.location.reload()} type="button">
            Retry
          </button>
        </div>
      </div>);
    }
    let page;
    if (path === "/quality/requirements") {
        page = <RequirementsPage />;
    }
    else if (path.startsWith("/quality/requirements/")) {
        const requirementId = decodeURIComponent(path.replace("/quality/requirements/", ""));
        page = <RequirementDetailsPage key={requirementId} requirementId={requirementId}/>;
    }
    else if (path === "/quality/reports") {
        page = <ReportsAnalyticsPage />;
    }
    else {
        page = <OverviewPage />;
    }
    return (<>
      {page}
    </>);
}
export default QualityApp;
