import { ChevronLeft, ChevronRight } from "lucide-react";

const RepositoryPagination = ({
  currentPage = 1,
  totalPages = 2,
  onPageChange,
}) => {
  return (
    <div className="flex items-center justify-between border-t border-slate-100 px-4 py-3">
      <p className="text-[9px] text-slate-500">
        Showing 1 to 8 of 12 repositories
      </p>

      <div className="flex items-center gap-1">
        <button
          type="button"
          disabled={currentPage === 1}
          onClick={() => onPageChange(currentPage - 1)}
          className="flex h-8 w-8 items-center justify-center rounded-md border border-slate-200 text-slate-500 disabled:opacity-40"
        >
          <ChevronLeft size={13} />
        </button>

        {Array.from({ length: totalPages }, (_, index) => index + 1).map(
          (page) => (
            <button
              key={page}
              type="button"
              onClick={() => onPageChange(page)}
              className={`
              flex h-8 w-8
              items-center justify-center
              rounded-md
              text-[10px]
              font-medium
              ${
                page === currentPage
                  ? "bg-blue-600 text-white shadow-sm"
                  : "border border-slate-200 text-slate-600 hover:bg-slate-50"
              }
            `}
            >
              {page}
            </button>
          ),
        )}

        <button
          type="button"
          disabled={currentPage === totalPages}
          onClick={() => onPageChange(currentPage + 1)}
          className="flex h-8 w-8 items-center justify-center rounded-md border border-slate-200 text-slate-500 disabled:opacity-40"
        >
          <ChevronRight size={13} />
        </button>
      </div>
    </div>
  );
};

export default RepositoryPagination;
