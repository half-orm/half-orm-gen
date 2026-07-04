<script lang="ts">
  let {
    count,
    active = false,
    ontoggle,
  }: {
    count: number;
    active?: boolean;
    ontoggle: () => void;
  } = $props();
</script>

{#if count > 0}
  <button type="button" onclick={ontoggle}
          class="text-xs font-medium px-2 py-1 rounded-full border transition-colors {active ? 'bg-blue-600 text-white border-blue-600' : 'bg-blue-50 text-blue-700 border-blue-200'}">
    +{count} new
  </button>
{/if}
