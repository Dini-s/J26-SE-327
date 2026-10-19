
import { ChevronDown, Eye, EyeOff, X } from "lucide-react";
import { useState } from "react";

const AddRepositoryPanel = ({ open, onClose, onAdd }) => {
  const [showToken, setShowToken] = useState(false);

  const [form, setForm] = useState({
    name: "",
    url: "",
    provider: "GitHub",
    branch: "main",
    token: "",
  });

  const handleChange = (field, value) => {
    setForm((prev) => ({
      ...prev,
      [field]: value,
    }));
  };

  const handleSubmit = (e) => {
    e.preventDefault();

    onAdd?.(form);

    setForm({
      name: "",
      url: "",
      provider: "GitHub",
      branch: "main",
      token: "",
    });

    onClose();
  };

  if (!open) {
    return null;
  }

  return (
    <>
      {/* Overlay */}
      <div
        className="
          fixed inset-0
          z-40
          bg-slate-900/20
          backdrop-blur-[1px]
        "
        onClick={onClose}
      />

      {/* Drawer */}
      <aside
        className="
          fixed
          right-0
          top-0
          z-50
          h-screen
          w-full
          max-w-[390px]
          overflow-y-auto
          border-l
          border-slate-200
          bg-white
          shadow-2xl
          animate-in
          slide-in-from-right
          duration-300
        "
      >
        {/* Header */}
        <div className="flex items-start justify-between border-b border-slate-100 p-5">
          <div>
            <h2 className="text-sm font-bold text-slate-900">Add Repository</h2>

            <p className="mt-1 text-[10px] text-slate-500">
              Connect a repository to ASPIRE
            </p>
          </div>

          <button
            type="button"
            onClick={onClose}
            className="
              rounded-lg
              p-1.5
              text-slate-400
              transition
              hover:bg-slate-100
              hover:text-slate-700
            "
          >
            <X size={18} />
          </button>
        </div>

        {/* Form */}
        <form onSubmit={handleSubmit} className="space-y-4 p-5">
          {/* Name */}
          <Field label="Repository Name" required>
            <input
              type="text"
              value={form.name}
              onChange={(e) => handleChange("name", e.target.value)}
              placeholder="e.g. Spring PetClinic"
              required
              className="input-style"
            />
          </Field>

          {/* URL */}
          <Field label="Repository URL" required>
            <input
              type="url"
              value={form.url}
              onChange={(e) => handleChange("url", e.target.value)}
              placeholder="https://github.com/owner/repo"
              required
              className="input-style"
            />
          </Field>

          {/* Provider */}
          <Field label="Provider" required>
            <div className="relative">
              <select
                value={form.provider}
                onChange={(e) => handleChange("provider", e.target.value)}
                className="input-style appearance-none pr-9"
              >
                <option>GitHub</option>
                <option>GitLab</option>
                <option>Bitbucket</option>
                <option>Azure DevOps</option>
              </select>

              <ChevronDown
                size={14}
                className="pointer-events-none absolute right-3 top-1/2 -translate-y-1/2 text-slate-400"
              />
            </div>
          </Field>

          {/* Branch */}
          <Field label="Branch">
            <div className="relative">
              <select
                value={form.branch}
                onChange={(e) => handleChange("branch", e.target.value)}
                className="input-style appearance-none pr-9"
              >
                <option>main</option>
                <option>master</option>
                <option>develop</option>
                <option>release</option>
              </select>

              <ChevronDown
                size={14}
                className="pointer-events-none absolute right-3 top-1/2 -translate-y-1/2 text-slate-400"
              />
            </div>
          </Field>

          {/* Token */}
          <Field label="Access Token (Optional)">
            <div className="relative">
              <input
                type={showToken ? "text" : "password"}
                value={form.token}
                onChange={(e) => handleChange("token", e.target.value)}
                placeholder="Enter token (optional)"
                className="input-style pr-10"
              />

              <button
                type="button"
                onClick={() => setShowToken((prev) => !prev)}
                className="
                  absolute
                  right-3
                  top-1/2
                  -translate-y-1/2
                  text-slate-400
                "
              >
                {showToken ? <EyeOff size={14} /> : <Eye size={14} />}
              </button>
            </div>

            <p className="mt-1.5 text-[10px] leading-4 text-slate-400">
              Token is stored securely and used to access private repositories.
            </p>
          </Field>

          {/* Actions */}
          <div className="flex gap-2 pt-4">
            <button
              type="button"
              onClick={onClose}
              className="
                h-10
                flex-1
                rounded-lg
                border
                border-slate-200
                bg-white
                text-xs
                font-medium
                text-slate-600
                transition
                hover:bg-slate-50
              "
            >
              Cancel
            </button>

            <button
              type="submit"
              className="
                h-10
                flex-1
                rounded-lg
                bg-blue-600
                text-xs
                font-semibold
                text-white
                transition
                hover:bg-blue-700
              "
            >
              Add Repository
            </button>
          </div>
        </form>
      </aside>
    </>
  );
};

const Field = ({ label, required, children }) => {
  return (
    <div>
      <label className="mb-1.5 block text-[10px] font-medium text-slate-600">
        {label}

        {required && <span className="ml-0.5 text-red-500">*</span>}
      </label>

      {children}
    </div>
  );
};

export default AddRepositoryPanel;
