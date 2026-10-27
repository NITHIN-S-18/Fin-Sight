export interface RecurringPaymentItem {
  id: string;
  name: string;
  provider: string;
  category: string;
  type: "Subscription" | "EMI" | "BNPL" | "Insurance" | "Rent" | "Mobile" | "Utility" | "Bill";
  status: "Active" | "Possible Trial" | "Inactive" | "Needs Confirmation";
  monthlyAmount: number;
  nextPaymentDate: string;
  daysUntilDue: number;
  source: "Detected" | "User Added";
  subtitle: string;
  autopay: boolean;
  frequency: string;
  notes?: string;
  backendId?: number;
  amount?: number;
  nextPaymentIso?: string;
}
