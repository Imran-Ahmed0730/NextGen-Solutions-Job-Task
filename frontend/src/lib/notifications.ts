import Swal, { type SweetAlertIcon } from 'sweetalert2';

export function showToast(icon: SweetAlertIcon, title: string, text?: string): void {
  void Swal.fire({
    toast: true,
    position: 'top-end',
    icon,
    title,
    text,
    showConfirmButton: false,
    timer: icon === 'error' ? 7000 : 5000,
    timerProgressBar: true,
  });
}

export function showErrorToast(message: string): void {
  showToast('error', message);
}

export function showSuccessToast(message: string): void {
  showToast('success', message);
}
