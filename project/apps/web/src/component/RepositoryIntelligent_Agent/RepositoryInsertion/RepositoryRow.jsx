import {
  Code2,
  Eye,
  MoreVertical,
  Play,
} from 'lucide-react';

import RepositoryStatus from './RepositoryStatus';

const providerStyles = {
  github: 'bg-black text-white',
  gitlab: 'bg-orange-500 text-white',
  azure: 'bg-blue-500 text-white',
  bitbucket: 'bg-blue-600 text-white',
};

const languageIcons = {
  Java: '☕',
  'Node.js': '⬡',
  'C#': '▣',
  Python: '🐍',
  React: '⚛',
};

const RepositoryRow = ({
  repository,
  onView,
  onAnalyze,
}) => {
  return (
    <div
      className="
        grid
        min-w-[1050px]
        grid-cols-[2.1fr_1fr_0.7fr_1.3fr_1.1fr_1fr_0.8fr]
        items-center
        border-b
        border-slate-100
        px-4
        py-4
        transition
        hover:bg-slate-50/70
      "
    >

      {/* Repository */}
      <div className="flex min-w-0 items-center gap-3">

        <div
          className={`
            flex h-8 w-8
            shrink-0
            items-center justify-center
            rounded-lg
            text-xs
            font-bold
            ${providerStyles[repository.providerType]}
          `}
        >
          {repository.provider === 'GitHub'
            ? '●'
            : repository.provider === 'GitLab'
              ? '◆'
              : repository.provider === 'Azure DevOps'
                ? '▣'
                : '◆'}
        </div>

        <div className="min-w-0">
          <p className="truncate text-[10px] font-semibold text-slate-800">
            {repository.name}
          </p>

          <p className="mt-0.5 truncate text-[10px] text-blue-500">
            {repository.url}
          </p>
        </div>
      </div>

      {/* Provider */}
      <div className="flex items-center gap-2 text-[10px] text-slate-600">
        <span
          className={`
            flex h-5 w-5
            items-center justify-center
            rounded-full
            text-[10px]
            ${providerStyles[repository.providerType]}
          `}
        >
          {repository.provider === 'GitHub'
            ? '●'
            : repository.provider === 'GitLab'
              ? '◆'
              : '◇'}
        </span>

        {repository.provider}
      </div>

      {/* Branch */}
      <div>
        <span className="rounded-md bg-blue-50 px-2 py-1 text-[11px] font-medium text-blue-600">
          {repository.branch}
        </span>
      </div>

      {/* Language */}
      <div className="flex items-center gap-2 text-[11px] text-slate-600">
        <span className="text-sm">
          {languageIcons[repository.language] || (
            <Code2 size={14} />
          )}
        </span>

        {repository.language}
        <span className="text-slate-300">•</span>
        {repository.technology}
      </div>

      {/* Status */}
      <div>
        <RepositoryStatus
          status={repository.status}
        />
      </div>

      {/* Last analyzed */}
      <div className="text-[11px] text-slate-500">
        <p>{repository.lastAnalyzed}</p>

        {repository.time && (
          <p>{repository.time}</p>
        )}
      </div>

      {/* Actions */}
      <div className="flex items-center gap-1">

        <button
          type="button"
          onClick={() => onView(repository)}
          className="
            rounded-md
            border border-slate-200
            px-2
            py-1
            text-[11px]
            font-medium
            text-blue-600
            transition
            hover:border-blue-200
            hover:bg-blue-50
          "
        >
          <Eye
            size={11}
            className="mr-1 inline"
          />
          View
        </button>

        <button
          type="button"
          onClick={() => onAnalyze(repository)}
          disabled={repository.status === 'Analyzing'}
          className="
            rounded-md
            border border-blue-200
            px-2
            py-1
            text-[11px]
            font-medium
            text-blue-600
            transition
            hover:bg-blue-600
            hover:text-white
            disabled:cursor-not-allowed
            disabled:opacity-40
          "
        >
          <Play
            size={10}
            className="mr-1 inline"
          />
          Analyze
        </button>

        <button
          type="button"
          className="rounded-md p-1.5 text-slate-400 hover:bg-slate-100 hover:text-slate-600"
          aria-label={`More actions for ${repository.name}`}
        >
          <MoreVertical size={14} />
        </button>

      </div>

    </div>
  );
};

export default RepositoryRow;