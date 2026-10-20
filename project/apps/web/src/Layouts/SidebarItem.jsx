import { pageRoutes } from "../routes/pageRoutes";
import { useState } from "react";
import {
  NavLink,
  useLocation,
} from "react-router-dom";

import {
  ChevronDown,
} from "lucide-react";


const numberStyles = {
  green: "bg-emerald-500",
  blue: "bg-blue-600",
  purple: "bg-violet-600",
  orange: "bg-orange-500",
};


const SidebarItem = ({
  item,
  collapsed,
  level = 0,
}) => {
  const location = useLocation();

  const pathname =
    location.pathname;

  const hasChildren =
    Array.isArray(item.children) &&
    item.children.length > 0;

  const canNavigate = pageRoutes.some((page) => page.path === item.path);

  const Icon =
    item.icon;


  const isItemActive = (
    target
  ) => {
    if (!target) {
      return false;
    }

    /*
      Requirement Details uses activePrefix because
      requirement ID changes:

      /quality/requirement-details/REQ-014
      /quality/requirement-details/REQ-021
      /quality/requirement-details/REQ-100
    */

    if (
      target.activePrefix
    ) {
      return pathname.startsWith(
        target.activePrefix
      );
    }

    if (!target.path) {
      return false;
    }

    /*
      EXACT matching only
    */

    return (
      pathname === target.path
    );
  };

  
  const hasActiveDescendant = (
    target
  ) => {
    if (
      !target?.children ||
      target.children.length === 0
    ) {
      return false;
    }

    return target.children.some(
      (child) => {
        if (
          isItemActive(child)
        ) {
          return true;
        }

        return (
          hasActiveDescendant(
            child
          )
        );
      }
    );
  };

  const itemActive =
    isItemActive(item);

  const childActive =
    hasActiveDescendant(
      item
    );

 
  const [expansion, setExpansion] = useState(null);
  const expanded = expansion?.pathname === pathname
    ? expansion.value
    : itemActive || childActive;
  const setExpanded = (update) => {
    setExpansion((previous) => ({
      pathname,
      value: update(previous?.pathname === pathname ? previous.value : itemActive || childActive),
    }));
  };

  const showActiveBackground =
    itemActive &&
    !hasChildren;

 
  const handleExpand = (
    event
  ) => {
    event.preventDefault();
    event.stopPropagation();

    setExpanded(
      (previous) =>
        !previous
    );
  };

  if (
    !item.path &&
    !hasChildren
  ) {
    return null;
  }


  return (
    <div
      className="
        relative
      "
    >
     
      <div
        className={`
          group
          relative
          flex
          items-center

          ${
            collapsed
              ? "justify-center"
              : ""
          }
        `}
      >
       
        {item.path ? (
          <NavLink
            to={canNavigate ? item.path : `${location.pathname}${location.search}${location.hash}`}
            onClick={(event) => {
              if (!canNavigate) {
                event.preventDefault();
                if (hasChildren) setExpanded((previous) => !previous);
              }
            }}
            aria-disabled={!canNavigate && !hasChildren ? true : undefined}
            end={
              !item.activePrefix
            }
            title={
              collapsed
                ? item.label
                : undefined
            }
            className={`
              relative
              flex
              min-w-0
              flex-1
              items-center
              gap-3
              rounded-lg
              px-3
              py-2
              text-xs
              transition-all
              duration-200

              ${
                showActiveBackground
                  ? `
                    bg-blue-600/90
                    text-white
                    shadow-md
                    shadow-blue-950/20
                  `
                  : `
                    text-slate-300
                    hover:bg-white/10
                    hover:text-white
                  `
              }

              ${
                collapsed
                  ? `
                    justify-center
                    px-2
                  `
                  : ""
              }
            `}
          >
            
            {showActiveBackground && (
              <span
                className="
                  absolute
                  left-0
                  top-1/2
                  h-5
                  w-0.5
                  -translate-y-1/2
                  rounded-full
                  bg-cyan-400
                "
              />
            )}

           
            {item.number &&
              !collapsed && (
                <span
                  className={`
                    flex
                    h-5
                    w-5
                    shrink-0
                    items-center
                    justify-center
                    rounded-full
                    text-[10px]
                    font-bold
                    text-white

                    ${
                      numberStyles[
                        item.numberColor
                      ] ||
                      "bg-blue-600"
                    }
                  `}
                >
                  {
                    item.number
                  }
                </span>
              )}

           
            {Icon && (
              <Icon
                size={16}
                strokeWidth={1.8}
                className="
                  shrink-0
                "
              />
            )}

                   {!Icon &&
              level > 0 &&
              !collapsed && (
                <span
                  className={`
                    h-[7px]
                    w-[7px]
                    shrink-0
                    rounded-full
                    border

                    ${
                      showActiveBackground
                        ? `
                          border-white
                          bg-white
                        `
                        : `
                          border-slate-400
                          bg-transparent
                        `
                    }
                  `}
                />
              )}

                {!collapsed && (
              <span
                className="
                  min-w-0
                  flex-1
                  truncate
                  font-medium
                "
              >
                {
                  item.label
                }
              </span>
            )}

           
          </NavLink>
        ) : (
         
          <button
            type="button"
            onClick={() =>
              setExpanded(
                (previous) =>
                  !previous
              )
            }
            className={`
              flex
              min-w-0
              flex-1
              items-center
              gap-3
              rounded-lg
              px-3
              py-2
              text-xs
              text-slate-300
              transition-all
              duration-200

              hover:bg-white/10
              hover:text-white

              ${
                collapsed
                  ? `
                    justify-center
                    px-2
                  `
                  : ""
              }
            `}
          >
            {Icon && (
              <Icon
                size={16}
                strokeWidth={1.8}
                className="
                  shrink-0
                "
              />
            )}

            {!collapsed && (
              <span
                className="
                  min-w-0
                  flex-1
                  truncate
                  text-left
                  font-medium
                "
              >
                {
                  item.label
                }
              </span>
            )}
          </button>
        )}

               {hasChildren &&
          !collapsed && (
            <button
              type="button"
              onClick={
                handleExpand
              }
              aria-label={
                `Expand ${item.label}`
              }
              className="
                absolute
                right-1
                flex
                h-[26px]
                w-[26px]
                items-center
                justify-center
                rounded
                text-slate-400
                transition

                hover:bg-white/10
                hover:text-white
              "
            >
              <ChevronDown
                size={13}
                className={`
                  transition-transform
                  duration-200

                  ${
                    expanded
                      ? "rotate-180"
                      : ""
                  }
                `}
              />
            </button>
          )}
      </div>

    
      {hasChildren &&
        !collapsed && (
          <div
            className={`
              grid
              transition-all
              duration-300

              ${
                expanded
                  ? "grid-rows-[1fr]"
                  : "grid-rows-[0fr]"
              }
            `}
          >
            <div
              className="
                overflow-hidden
              "
            >
              <div
                className={`
                  ml-4
                  mt-1
                  border-l
                  border-white/10
                  pl-2

                  ${
                    expanded
                      ? "opacity-100"
                      : "opacity-0"
                  }

                  transition-opacity
                  duration-200
                `}
              >
                {item.children.map(
                  (
                    child,
                    index
                  ) => (
                    <SidebarItem
                      key={`${child.label}-${index}`}
                      item={child}
                      collapsed={
                        collapsed
                      }
                      level={
                        level + 1
                      }
                    />
                  )
                )}
              </div>
            </div>
          </div>
        )}
    </div>
  );
};

export default SidebarItem;