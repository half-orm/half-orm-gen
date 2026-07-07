
  constructor() {
    effect(() => {
      const fkAuto = this.silo.fkAutoFields('POST');
      for (const [field, target] of Object.entries(this.fkTargets)) {
        if (fkAuto[field] === 'select') this.registry.get(target).list();
      }
    });
  }