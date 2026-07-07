import { Component } from '@angular/core';
import { RouterLink } from '@angular/router';

@Component({
  selector: 'app-home',
  standalone: true,
  imports: [RouterLink],
  template: `
    <div class="flex flex-col items-center justify-center h-full bg-gray-50 py-16">
      <div class="relative group flex items-center gap-6 mb-6">
        <img src="logo.png" alt="halfORM" class="h-30 w-auto" />
        <img src="logo-chapeau.png" alt="" class="absolute inset-0 h-30 w-auto transition-opacity duration-[2000ms] opacity-100 group-hover:opacity-0" />
      </div>
      <h1 class="text-3xl font-bold text-gray-800 mb-2">halfORM Backoffice</h1>
      <p class="text-gray-500">Powered by Angular
      </p>
      <div class="mb-8">
        <img src="angular_200x200.png" alt="Angular" class="h-10 w-auto" />
      </div>
      <a [routerLink]="['/ho_bo']"
         class="bg-red-600 text-white px-6 py-3 rounded-lg hover:bg-red-700 font-medium transition-colors">
        Open Backoffice →
      </a>
    </div>
  `
})
export class HomeComponent {}
