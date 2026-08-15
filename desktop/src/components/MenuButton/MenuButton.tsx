// Adapted from ../_reference/eigent/src/components/MenuButton/MenuButton.tsx.
// Keeps the MenuToggleGroup/MenuToggleItem API and Radix ToggleGroup behavior,
// while using local CSS classes instead of Eigent's Tailwind token pipeline.

import * as ToggleGroupPrimitive from '@radix-ui/react-toggle-group';
import * as React from 'react';

type MenuToggleSize = 'xs' | 'sm' | 'md' | 'iconxs';
type MenuToggleVariant = 'default' | 'clear' | 'info';

interface MenuToggleStyleProps {
  size?: MenuToggleSize;
  variant?: MenuToggleVariant;
}

const MenuToggleGroupContext = React.createContext<MenuToggleStyleProps>({
  variant: 'default',
  size: 'md',
});

function classNames(...values: Array<string | false | null | undefined>): string {
  return values.filter(Boolean).join(' ');
}

type MenuToggleGroupProps = React.ComponentPropsWithoutRef<typeof ToggleGroupPrimitive.Root> &
  MenuToggleStyleProps;

export const MenuToggleGroup = React.forwardRef<
  React.ElementRef<typeof ToggleGroupPrimitive.Root>,
  MenuToggleGroupProps
>(
  (
    { className, variant = 'default', size = 'md', children, orientation = 'vertical', ...props },
    ref
  ) => (
    <ToggleGroupPrimitive.Root
      ref={ref}
      orientation={orientation}
      className={classNames(
        'menu-toggle-group',
        orientation === 'vertical' ? 'vertical' : 'horizontal',
        className
      )}
      {...props}
    >
      <MenuToggleGroupContext.Provider value={{ variant, size }}>
        {children}
      </MenuToggleGroupContext.Provider>
    </ToggleGroupPrimitive.Root>
  )
);

MenuToggleGroup.displayName = 'MenuToggleGroup';

type MenuToggleItemProps = React.ComponentPropsWithoutRef<typeof ToggleGroupPrimitive.Item> &
  MenuToggleStyleProps & {
    icon?: React.ReactNode;
    subIcon?: React.ReactNode;
    showSubIcon?: boolean;
    rightElement?: React.ReactNode;
  };

export const MenuToggleItem = React.forwardRef<
  React.ElementRef<typeof ToggleGroupPrimitive.Item>,
  MenuToggleItemProps
>(
  (
    {
      className,
      children,
      size,
      icon,
      variant,
      subIcon,
      showSubIcon = false,
      rightElement,
      ...props
    },
    ref
  ) => {
    const context = React.useContext(MenuToggleGroupContext);
    const currentVariant = variant || context.variant || 'default';
    const currentSize = size || context.size || 'md';

    return (
      <ToggleGroupPrimitive.Item
        ref={ref}
        className={classNames(
          'menu-toggle-item',
          `variant-${currentVariant}`,
          `size-${currentSize}`,
          className
        )}
        {...props}
      >
        <span className={classNames('menu-toggle-content', rightElement ? 'with-right' : '')}>
          <span className="menu-toggle-main">
            {icon}
            {children}
          </span>
          {rightElement ? (
            <span
              className="menu-toggle-right"
              onClick={(event) => event.stopPropagation()}
            >
              {rightElement}
            </span>
          ) : null}
        </span>
        {showSubIcon && subIcon ? (
          <span className="menu-toggle-sub-icon">{subIcon}</span>
        ) : null}
      </ToggleGroupPrimitive.Item>
    );
  }
);

MenuToggleItem.displayName = 'MenuToggleItem';
