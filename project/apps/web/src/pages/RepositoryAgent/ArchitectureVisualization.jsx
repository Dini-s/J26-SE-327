import { useState } from "react";
import ContentHeader from "../../component/common/ContentHeader";
import ArchitectureDistribution from "../../component/RepositoryIntelligent_Agent/architecture/archtectureVisual/ArchitectureDistribution";
import ArchitectureGraph from "../../component/RepositoryIntelligent_Agent/architecture/archtectureVisual/ArchitectureGraph";
import ArchitectureLegend from "../../component/RepositoryIntelligent_Agent/architecture/archtectureVisual/ArchitectureLegend";
import ArchitectureStatCard from "../../component/RepositoryIntelligent_Agent/architecture/archtectureVisual/ArchitectureStatCard";
import ArchitectureToolbar from "../../component/RepositoryIntelligent_Agent/architecture/archtectureVisual/ArchitectureToolbar";
import LayerSummary from "../../component/RepositoryIntelligent_Agent/architecture/archtectureVisual/LayerSummary";
import RecentArchitectureChanges from "../../component/RepositoryIntelligent_Agent/architecture/archtectureVisual/RecentArchitectureChanges";
import SelectedModulePanel from "../../component/RepositoryIntelligent_Agent/architecture/archtectureVisual/SelectedModulePanel";
import ViolationOverview from "../../component/RepositoryIntelligent_Agent/architecture/archtectureVisual/ViolationOverview";
import { architectureStats,selectedModule as defaultModule } from "../../data/architectureData";

const ArchitectureVisualization = () => {
  const [selectedModule, setSelectedModule] = useState(defaultModule);

  return (
    <div className="mx-auto w-full max-w-[1600px]">
      <header className="mb-4">
        <ContentHeader
          title={"Architecture Visualization"}
          subtitle={
            "Visualize system architecture, dependencies, layers, and violations"
          }
        />
      </header>

      <section
        className="
          grid grid-cols-1
          gap-2
          sm:grid-cols-2
          lg:grid-cols-3
          xl:grid-cols-6
        "
      >
        {architectureStats.map((stat) => (
          <ArchitectureStatCard key={stat.title} {...stat} />
        ))}
      </section>
      <section
        className="
          mt-2
          grid grid-cols-1
          gap-2
          xl:grid-cols-[minmax(0,1.9fr)_minmax(330px,0.8fr)]
        "
      >
        {/* Graph */}
        <div
          className="
            relative
            overflow-hidden
            rounded-xl
            border
            border-slate-200
            bg-white
            shadow-sm
          "
        >
          <ArchitectureToolbar />

          <ArchitectureLegend />

          <ArchitectureGraph onSelectModule={setSelectedModule} />
        </div>

        {/* Selected Module */}
        <SelectedModulePanel module={selectedModule} />
      </section>
      <section
        className="
          mt-2
          grid grid-cols-1
          gap-2
          lg:grid-cols-2
          xl:grid-cols-[1fr_1fr_1fr_1.25fr]
        "
      >
        <ArchitectureDistribution />

        <LayerSummary />

        <ViolationOverview />

        <RecentArchitectureChanges />
      </section>
    </div>
  );
};

export default ArchitectureVisualization;
