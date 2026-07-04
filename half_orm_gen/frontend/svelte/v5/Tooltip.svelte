<script lang="ts">
  import type { Snippet } from 'svelte';

  let {
    trigger,
    children,
    align = 'left',
  }: {
    trigger: Snippet;
    children: Snippet;
    align?: 'left' | 'right';
  } = $props();
</script>

<div class="group relative inline-flex">
  {@render trigger()}
  <div class="pointer-events-none invisible absolute top-full z-20 mt-2 w-max max-w-xs rounded-lg border border-gray-200 bg-white p-3 text-[11px] leading-relaxed text-gray-700 shadow-lg opacity-0 transition-opacity duration-150 group-hover:visible group-hover:opacity-100 {align === 'right' ? 'right-0' : 'left-0'}">
    <div class="absolute -top-1 h-2 w-2 rotate-45 border-l border-t border-gray-200 bg-white {align === 'right' ? 'right-2' : 'left-2'}"></div>
    {@render children()}
  </div>
</div>
