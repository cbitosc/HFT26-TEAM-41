type Dir = { dirs: Map<string, Dir>; files: string[] }; // files: full paths

function buildTree(paths: string[]): Dir {
  const root: Dir = { dirs: new Map(), files: [] };
  for (const path of paths) {
    const parts = path.split("/");
    let dir = root;
    for (const part of parts.slice(0, -1)) {
      if (!dir.dirs.has(part)) dir.dirs.set(part, { dirs: new Map(), files: [] });
      dir = dir.dirs.get(part)!;
    }
    dir.files.push(path);
  }
  return root;
}

type Props = {
  paths: string[];
  active: string;
  readOnlyReason: (path: string) => string | null;
  onOpen: (path: string) => void;
};

function DirView({ dir, depth, ...props }: Props & { dir: Dir; depth: number }) {
  const pad = { paddingLeft: `${0.75 + depth * 0.75}rem` };
  return (
    <>
      {[...dir.dirs.entries()]
        .sort(([a], [b]) => a.localeCompare(b))
        .map(([name, sub]) => (
          <div key={name}>
            <div style={pad} className="py-0.5 text-gray-500">
              {name}/
            </div>
            <DirView dir={sub} depth={depth + 1} {...props} />
          </div>
        ))}
      {[...dir.files].sort().map((path) => {
        const reason = props.readOnlyReason(path);
        return (
          <button
            key={path}
            style={pad}
            title={reason ?? path}
            onClick={() => props.onOpen(path)}
            className={`block w-full truncate py-0.5 pr-2 text-left ${path === props.active ? "bg-blue-50 font-medium text-blue-800" : "hover:bg-gray-50"} ${reason ? "text-gray-400" : ""}`}
          >
            {path.split("/").pop()}
            {reason && <span className="ml-1 text-xs">🔒</span>}
          </button>
        );
      })}
    </>
  );
}

export default function FileTree(props: Props) {
  return <DirView dir={buildTree(props.paths)} depth={0} {...props} />;
}
