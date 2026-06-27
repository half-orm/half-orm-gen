<script lang="ts">
  import { tick, untrack } from 'svelte';
  import type { Verb, PermMatrix } from '$lib/generated/stores/schema.types';
  import PermissionsFields from '$lib/generated/PermissionsFields.svelte';

  let { permissions = {}, roles = [], defaultOpen = false }: {
    permissions: PermMatrix;
    roles: string[];
    defaultOpen?: boolean;
  } = $props();

  const verbs: Verb[] = ['GET', 'POST', 'PUT', 'DELETE'];
  let open = $state(untrack(() => defaultOpen));
  let hovered: { role: string; verb: Verb } | null = $state(null);
  let tooltipEl: HTMLElement;

  async function onEnter(e: MouseEvent, role: string, verb: Verb) {
    if (verb === 'DELETE') return;
    hovered = { role, verb };
    await tick();
    const rect = (e.currentTarget as HTMLElement).getBoundingClientRect();
    tooltipEl.style.left = `${rect.left + rect.width / 2}px`;
    tooltipEl.style.top = `${rect.top - 8}px`;
    tooltipEl.style.transform = 'translate(-50%, -100%)';
    tooltipEl.showPopover();
  }

  function onLeave() {
    tooltipEl.hidePopover();
    hovered = null;
  }
</script>

<div class="mb-3">
  <button onclick={() => (open = !open)}
          class="text-xs text-gray-400 hover:text-gray-600 flex items-center gap-1 select-none">
    <span class="font-medium tracking-wide">Permissions</span>
    <span class="text-[10px]">{open ? '▲' : '▼'}</span>
  </button>
  {#if open}
    <div class="mt-2 border rounded-lg bg-white inline-block shadow-sm">
      <table class="text-xs">
        <thead>
          <tr class="border-b bg-gray-50">
            <th class="px-4 py-2 text-left font-medium text-gray-500 border-r">Role</th>
            {#each verbs as verb}
              <th class="px-4 py-2 text-center font-medium text-gray-500 w-16">{verb}</th>
            {/each}
          </tr>
        </thead>
        <tbody>
          {#each roles as role}
            <tr class="border-t">
              <td class="px-4 py-2 font-mono text-gray-700 border-r">{role}</td>
              {#each verbs as verb}
                <td class="px-4 py-2 text-center">
                  {#if permissions[role]?.[verb]}
                    <span role="img" aria-label="{role} {verb} allowed"
                          class="text-green-600 cursor-default select-none"
                          onmouseenter={(e) => onEnter(e, role, verb)}
                          onmouseleave={onLeave}>✓</span>
                  {:else}
                    <span class="text-gray-300 select-none">—</span>
                  {/if}
                </td>
              {/each}
            </tr>
          {/each}
        </tbody>
      </table>
    </div>
  {/if}
</div>

<!-- shared popover — always in DOM so bind:this resolves even before first open -->
<div bind:this={tooltipEl} popover="manual"
     style="padding:0;border:none;background:transparent;inset:unset;margin:0;overflow:visible">
  {#if hovered}
    <div class="bg-white border rounded-lg shadow-xl px-3 py-2.5">
      <div class="text-[10px] font-semibold text-gray-400 uppercase tracking-widest mb-2">
        {hovered.role} · {hovered.verb}
      </div>
      <PermissionsFields access={permissions[hovered.role]?.[hovered.verb]} verb={hovered.verb} />
    </div>
  {/if}
</div>
