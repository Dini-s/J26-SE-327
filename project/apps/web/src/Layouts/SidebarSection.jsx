

const SidebarSection = ({ label, collapsed }) => {
  if (collapsed) {
    return (
      <div className="my-3 h-px bg-white/10" />
    );
  }

  return (
    <div className="px-3 pb-2 pt-5">
      <p className="text-[10px] font-semibold tracking-wider text-slate-500">
        {label}
      </p>
    </div>
  );
};

export default SidebarSection;