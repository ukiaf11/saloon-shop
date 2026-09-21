/**
 * Owner-panel response schemas. These carry what the owner needs to check
 * money against their UPI app -- full phone numbers and full UPI references --
 * so they are only ever fetched with a signed-in owner's token.
 */

import { z } from "zod";

import { orderLuckySchema } from "./api";

export const ownerUserSchema = z.object({
  email: z.string(),
  full_name: z.string(),
  role: z.enum(["OWNER", "MANAGER", "RECEPTIONIST"]),
  mfa_enabled: z.boolean(),
});
export type OwnerUser = z.infer<typeof ownerUserSchema>;

export const sessionSchema = z.object({
  token: z.string().min(20),
  expires_at: z.string(),
  user: ownerUserSchema,
});

export const meSchema = z.object({
  user: ownerUserSchema,
  expires_at: z.string(),
});

export const paymentSettingsSchema = z.object({
  method: z.enum(["upi_qr", "gateway", "unavailable"]),
  gateway_configured: z.boolean(),
  qr: z
    .object({
      version: z.string(),
      width: z.number().int().nullable(),
      height: z.number().int().nullable(),
      updated_at: z.string().nullable(),
    })
    .nullable(),
  upi_id: z.string(),
  payee_name: z.string(),
});
export type PaymentSettings = z.infer<typeof paymentSettingsSchema>;

const ownerRefundSummarySchema = z.object({
  id: z.uuid(),
  amount_paise: z.number().int().positive(),
  status: z.enum(["pending", "sent"]),
  method: z.enum(["UPI", "CASH"]).nullable(),
  reference: z.string().nullable(),
});

export const ownerPaymentSchema = z.object({
  id: z.uuid(),
  status: z.enum(["awaiting_confirmation", "confirmed", "rejected"]),
  reference: z.string(),
  amount_paise: z.number().int().nonnegative(),
  submitted_at: z.string(),
  decided_at: z.string().nullable(),
  rejection_reason: z.string().nullable(),
  order: z.object({
    id: z.uuid(),
    public_order_number: z.string(),
    status: z.string(),
    total_paise: z.number().int().nonnegative(),
    created_at: z.string(),
    items: z.array(z.object({ name: z.string(), quantity: z.number().int().positive() })),
  }),
  customer: z.object({ name: z.string(), phone: z.string() }),
  draw: orderLuckySchema,
  draw_day_over: z.boolean(),
  refund: ownerRefundSummarySchema.nullable(),
});
export type OwnerPayment = z.infer<typeof ownerPaymentSchema>;

export const ownerPaymentListSchema = z.object({ results: z.array(ownerPaymentSchema) });

export const ownerRefundSchema = z.object({
  id: z.uuid(),
  status: z.enum(["pending", "sent"]),
  amount_paise: z.number().int().positive(),
  reason: z.string(),
  created_at: z.string(),
  method: z.enum(["UPI", "CASH"]).nullable(),
  reference: z.string().nullable(),
  sent_at: z.string().nullable(),
  order: z.object({
    id: z.uuid(),
    public_order_number: z.string(),
    total_paise: z.number().int().nonnegative(),
  }),
  customer: z.object({ name: z.string(), phone: z.string() }),
  payment_reference: z.string().nullable(),
  participant_number: z.number().int().positive().nullable(),
  free_services: z.array(z.string()),
});
export type OwnerRefund = z.infer<typeof ownerRefundSchema>;

export const ownerRefundListSchema = z.object({ results: z.array(ownerRefundSchema) });

export const okSchema = z.record(z.string(), z.unknown());
