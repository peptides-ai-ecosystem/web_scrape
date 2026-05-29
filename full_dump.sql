--
-- PostgreSQL database dump
--

\restrict vXMbyM7I8HejD4bN7dtFBxbvXtVwr9fFbADUWnzwmtjpMkmiZAyXXThbcJSg7sh

-- Dumped from database version 17.6
-- Dumped by pg_dump version 17.9

SET statement_timeout = 0;
SET lock_timeout = 0;
SET idle_in_transaction_session_timeout = 0;
SET transaction_timeout = 0;
SET client_encoding = 'UTF8';
SET standard_conforming_strings = on;
SELECT pg_catalog.set_config('search_path', '', false);
SET check_function_bodies = false;
SET xmloption = content;
SET client_min_messages = warning;
SET row_security = off;

--
-- Name: public; Type: SCHEMA; Schema: -; Owner: -
--

CREATE SCHEMA public;


--
-- Name: analytics_app_id; Type: TYPE; Schema: public; Owner: -
--

CREATE TYPE public.analytics_app_id AS ENUM (
    'wiki',
    'calculator',
    'pepti_price',
    'sds',
    'admin'
);


--
-- Name: analytics_event_type; Type: TYPE; Schema: public; Owner: -
--

CREATE TYPE public.analytics_event_type AS ENUM (
    'page_view',
    'click',
    'search',
    'calculate',
    'compare',
    'share',
    'download',
    'submit',
    'error',
    'other'
);


--
-- Name: benefit_category; Type: TYPE; Schema: public; Owner: -
--

CREATE TYPE public.benefit_category AS ENUM (
    'performance',
    'recovery',
    'longevity',
    'cognitive',
    'metabolic',
    'cosmetic'
);


--
-- Name: credit_transaction_type; Type: TYPE; Schema: public; Owner: -
--

CREATE TYPE public.credit_transaction_type AS ENUM (
    'purchase',
    'deduct',
    'refund',
    'admin_grant',
    'admin_deduct'
);


--
-- Name: delivery_status; Type: TYPE; Schema: public; Owner: -
--

CREATE TYPE public.delivery_status AS ENUM (
    'pending',
    'sent',
    'delivered',
    'failed',
    'bounced'
);


--
-- Name: effectiveness_tag; Type: TYPE; Schema: public; Owner: -
--

CREATE TYPE public.effectiveness_tag AS ENUM (
    'most_effective',
    'effective',
    'moderate'
);


--
-- Name: evidence_level; Type: TYPE; Schema: public; Owner: -
--

CREATE TYPE public.evidence_level AS ENUM (
    'strong',
    'moderate',
    'preliminary',
    'anecdotal'
);


--
-- Name: fda_approval_status; Type: TYPE; Schema: public; Owner: -
--

CREATE TYPE public.fda_approval_status AS ENUM (
    'approved',
    'investigational',
    'not_approved',
    'withdrawn'
);


--
-- Name: frequency; Type: TYPE; Schema: public; Owner: -
--

CREATE TYPE public.frequency AS ENUM (
    'rare',
    'uncommon',
    'common',
    'very_common'
);


--
-- Name: interaction_type; Type: TYPE; Schema: public; Owner: -
--

CREATE TYPE public.interaction_type AS ENUM (
    'synergistic',
    'antagonistic',
    'neutral',
    'caution'
);


--
-- Name: peptide_type; Type: TYPE; Schema: public; Owner: -
--

CREATE TYPE public.peptide_type AS ENUM (
    'linear',
    'cyclic',
    'branched',
    'modified'
);


--
-- Name: reference_type; Type: TYPE; Schema: public; Owner: -
--

CREATE TYPE public.reference_type AS ENUM (
    'study',
    'citation'
);


--
-- Name: research_level; Type: TYPE; Schema: public; Owner: -
--

CREATE TYPE public.research_level AS ENUM (
    'preclinical',
    'phase_1',
    'phase_2',
    'phase_3',
    'approved',
    'off_label'
);


--
-- Name: sds_fetch_status; Type: TYPE; Schema: public; Owner: -
--

CREATE TYPE public.sds_fetch_status AS ENUM (
    'pending',
    'partial',
    'complete',
    'failed'
);


--
-- Name: severity_level; Type: TYPE; Schema: public; Owner: -
--

CREATE TYPE public.severity_level AS ENUM (
    'low',
    'medium',
    'high',
    'critical'
);


--
-- Name: side_effect_severity; Type: TYPE; Schema: public; Owner: -
--

CREATE TYPE public.side_effect_severity AS ENUM (
    'mild',
    'moderate',
    'severe',
    'critical'
);


--
-- Name: stock_status; Type: TYPE; Schema: public; Owner: -
--

CREATE TYPE public.stock_status AS ENUM (
    'in_stock',
    'out_of_stock'
);


--
-- Name: suggestion_status; Type: TYPE; Schema: public; Owner: -
--

CREATE TYPE public.suggestion_status AS ENUM (
    'pending',
    'under_review',
    'implemented',
    'rejected',
    'duplicate'
);


--
-- Name: wada_status; Type: TYPE; Schema: public; Owner: -
--

CREATE TYPE public.wada_status AS ENUM (
    'prohibited',
    'monitored',
    'allowed',
    'unknown'
);


--
-- Name: authorize(text); Type: FUNCTION; Schema: public; Owner: -
--

CREATE FUNCTION public.authorize(requested_role text) RETURNS boolean
    LANGUAGE plpgsql STABLE SECURITY DEFINER
    SET search_path TO ''
    AS $$
DECLARE
  user_role text;
BEGIN
  -- Fetch user role from JWT claims
  SELECT (auth.jwt() ->> 'user_role') INTO user_role;
  
  -- Admin has all permissions
  IF user_role = 'admin' THEN
    RETURN true;
  END IF;
  
  -- Check if user has the requested role
  RETURN user_role = requested_role;
END;
$$;


--
-- Name: custom_access_token_hook(jsonb); Type: FUNCTION; Schema: public; Owner: -
--

CREATE FUNCTION public.custom_access_token_hook(event jsonb) RETURNS jsonb
    LANGUAGE plpgsql STABLE
    AS $$
DECLARE
  claims jsonb;
  v_user_role text;
  v_app_context text;
BEGIN
  -- Fetch the user's primary role from user_roles table
  -- We use the most recently granted active role
  SELECT 
    r.name,
    ur.app_context
  INTO v_user_role, v_app_context
  FROM public.user_roles ur
  JOIN public.roles r ON r.id = ur.role_id
  WHERE ur.user_id = (
    SELECT u.id FROM public.users u 
    WHERE u.auth_user_id = (event ->> 'user_id')
    LIMIT 1
  )
  AND ur.is_active = true
  ORDER BY ur.granted_at DESC
  LIMIT 1;

  -- Get existing claims
  claims := event -> 'claims';

  -- Inject user_role claim
  IF v_user_role IS NOT NULL THEN
    claims := jsonb_set(claims, '{user_role}', to_jsonb(v_user_role));
  ELSE
    claims := jsonb_set(claims, '{user_role}', '"user"'); -- Default to 'user'
  END IF;

  -- Inject app_context claim
  IF v_app_context IS NOT NULL THEN
    claims := jsonb_set(claims, '{app_context}', to_jsonb(v_app_context));
  ELSE
    claims := jsonb_set(claims, '{app_context}', '"global"');
  END IF;

  -- Update the event with modified claims
  event := jsonb_set(event, '{claims}', claims);

  RETURN event;
END;
$$;


--
-- Name: handle_new_user(); Type: FUNCTION; Schema: public; Owner: -
--

CREATE FUNCTION public.handle_new_user() RETURNS trigger
    LANGUAGE plpgsql SECURITY DEFINER
    SET search_path TO 'public'
    AS $$
DECLARE
  v_app_context text;
  v_user_role_id integer;
  v_target_user_id uuid;
  v_is_influencer boolean;
  v_existing_public_user_id uuid;
BEGIN
  SELECT id INTO v_existing_public_user_id
  FROM public.users
  WHERE email = new.email
  LIMIT 1;

  IF v_existing_public_user_id IS NOT NULL THEN
    v_target_user_id := v_existing_public_user_id;

    RAISE NOTICE 'handle_new_user: linking auth user % to existing public.users %', new.id, v_existing_public_user_id;

    UPDATE public.users
    SET
      auth_user_id = new.id::text,
      updated_at = now(),
      email_verified = CASE WHEN new.email_confirmed_at IS NOT NULL THEN true ELSE email_verified END,
      image_url = COALESCE(image_url, new.raw_user_meta_data ->> 'avatar_url')
    WHERE id = v_existing_public_user_id;
  ELSE
    v_target_user_id := gen_random_uuid();

    INSERT INTO public.users (
      id,
      auth_user_id,
      email,
      first_name,
      last_name,
      image_url,
      email_verified,
      created_at,
      updated_at
    )
    VALUES (
      v_target_user_id,
      new.id::text,
      new.email,
      COALESCE(new.raw_user_meta_data ->> 'first_name', new.raw_user_meta_data ->> 'full_name', ''),
      COALESCE(new.raw_user_meta_data ->> 'last_name', ''),
      new.raw_user_meta_data ->> 'avatar_url',
      CASE WHEN new.email_confirmed_at IS NOT NULL THEN true ELSE false END,
      now(),
      now()
    );
  END IF;

  v_app_context := COALESCE(new.raw_user_meta_data ->> 'app_context', 'wiki');

  SELECT id INTO v_user_role_id FROM public.roles WHERE name = 'user' LIMIT 1;

  IF v_user_role_id IS NULL THEN
    v_user_role_id := 6;
  END IF;

  INSERT INTO public.user_roles (
    user_id,
    role_id,
    app_context,
    is_active,
    granted_at,
    created_at
  )
  VALUES (
    v_target_user_id,
    v_user_role_id,
    v_app_context,
    true,
    now(),
    now()
  )
  ON CONFLICT (user_id, role_id, app_context) DO NOTHING;

  IF v_app_context IN ('wiki', 'wiki-influencer', 'sds', 'global') THEN
    v_is_influencer := COALESCE((new.raw_user_meta_data ->> 'is_influencer')::boolean, false);

    INSERT INTO public.wiki_user_profiles (
      user_id,
      is_influencer,
      profile_visibility,
      created_at,
      updated_at
    )
    VALUES (
      v_target_user_id,
      v_is_influencer,
      'public',
      now(),
      now()
    )
    ON CONFLICT (user_id) DO UPDATE SET
      is_influencer = CASE WHEN EXCLUDED.is_influencer = true THEN true ELSE wiki_user_profiles.is_influencer END,
      updated_at = now();

    IF v_is_influencer THEN
      INSERT INTO public.user_roles (
        user_id,
        role_id,
        app_context,
        is_active,
        granted_at,
        created_at
      )
      SELECT
        v_target_user_id,
        r.id,
        v_app_context,
        true,
        now(),
        now()
      FROM public.roles r
      WHERE r.name = 'influencer'
      ON CONFLICT (user_id, role_id, app_context) DO NOTHING;
    END IF;
  END IF;

  RETURN new;
EXCEPTION WHEN OTHERS THEN
  RAISE WARNING 'Error in handle_new_user: % (SQLSTATE %)', SQLERRM, SQLSTATE;
  RETURN new;
END;
$$;


--
-- Name: set_updated_at(); Type: FUNCTION; Schema: public; Owner: -
--

CREATE FUNCTION public.set_updated_at() RETURNS trigger
    LANGUAGE plpgsql
    AS $$
BEGIN
  NEW.updated_at = NOW();
  RETURN NEW;
END;
$$;


SET default_tablespace = '';

SET default_table_access_method = heap;

--
-- Name: administration_methods; Type: TABLE; Schema: public; Owner: -
--

CREATE TABLE public.administration_methods (
    id integer NOT NULL,
    name character varying(100) NOT NULL,
    description text,
    icon text,
    color_bg character varying(7),
    color_text character varying(7),
    sort_order integer DEFAULT 0 NOT NULL,
    is_active boolean DEFAULT true NOT NULL,
    deleted_at timestamp with time zone,
    created_at timestamp with time zone DEFAULT now(),
    updated_at timestamp with time zone DEFAULT now(),
    CONSTRAINT admin_methods_name_not_empty CHECK ((length(TRIM(BOTH FROM name)) > 0))
);


--
-- Name: administration_methods_id_seq; Type: SEQUENCE; Schema: public; Owner: -
--

CREATE SEQUENCE public.administration_methods_id_seq
    AS integer
    START WITH 1
    INCREMENT BY 1
    NO MINVALUE
    NO MAXVALUE
    CACHE 1;


--
-- Name: administration_methods_id_seq; Type: SEQUENCE OWNED BY; Schema: public; Owner: -
--

ALTER SEQUENCE public.administration_methods_id_seq OWNED BY public.administration_methods.id;


--
-- Name: app_analytics; Type: TABLE; Schema: public; Owner: -
--

CREATE TABLE public.app_analytics (
    id integer NOT NULL,
    app_id public.analytics_app_id NOT NULL,
    event_type public.analytics_event_type NOT NULL,
    entity_type character varying(100),
    entity_id character varying(100),
    user_id character varying(128),
    session_id character varying(128),
    metadata jsonb,
    ip_address character varying(45),
    user_agent text,
    "timestamp" timestamp with time zone DEFAULT now() NOT NULL,
    created_at timestamp with time zone DEFAULT now()
);


--
-- Name: app_analytics_id_seq; Type: SEQUENCE; Schema: public; Owner: -
--

CREATE SEQUENCE public.app_analytics_id_seq
    AS integer
    START WITH 1
    INCREMENT BY 1
    NO MINVALUE
    NO MAXVALUE
    CACHE 1;


--
-- Name: app_analytics_id_seq; Type: SEQUENCE OWNED BY; Schema: public; Owner: -
--

ALTER SEQUENCE public.app_analytics_id_seq OWNED BY public.app_analytics.id;


--
-- Name: app_credit_costs; Type: TABLE; Schema: public; Owner: -
--

CREATE TABLE public.app_credit_costs (
    id uuid DEFAULT gen_random_uuid() NOT NULL,
    feature_key character varying(100) NOT NULL,
    credits_required integer NOT NULL,
    description text,
    is_active boolean DEFAULT true NOT NULL,
    created_at timestamp with time zone DEFAULT now(),
    updated_at timestamp with time zone DEFAULT now(),
    app_source character varying(50) NOT NULL,
    CONSTRAINT app_credit_costs_credits_positive CHECK ((credits_required > 0)),
    CONSTRAINT app_credit_costs_feature_key_format CHECK (((feature_key)::text ~ '^[a-z][a-z0-9_]*$'::text))
);


--
-- Name: app_sources; Type: TABLE; Schema: public; Owner: -
--

CREATE TABLE public.app_sources (
    code character varying(50) NOT NULL,
    label text NOT NULL,
    is_active boolean DEFAULT true NOT NULL,
    created_at timestamp with time zone DEFAULT now() NOT NULL
);


--
-- Name: application_places; Type: TABLE; Schema: public; Owner: -
--

CREATE TABLE public.application_places (
    id integer NOT NULL,
    name character varying(100) NOT NULL,
    description text,
    anatomical_region character varying(100),
    absorption_rate character varying(50),
    icon text,
    color_bg character varying(7),
    color_text character varying(7),
    sort_order integer DEFAULT 0 NOT NULL,
    is_active boolean DEFAULT true NOT NULL,
    deleted_at timestamp with time zone,
    created_at timestamp with time zone DEFAULT now(),
    updated_at timestamp with time zone DEFAULT now(),
    instructions text,
    CONSTRAINT application_places_name_not_empty CHECK ((length(TRIM(BOTH FROM name)) > 0))
);


--
-- Name: application_places_id_seq; Type: SEQUENCE; Schema: public; Owner: -
--

CREATE SEQUENCE public.application_places_id_seq
    AS integer
    START WITH 1
    INCREMENT BY 1
    NO MINVALUE
    NO MAXVALUE
    CACHE 1;


--
-- Name: application_places_id_seq; Type: SEQUENCE OWNED BY; Schema: public; Owner: -
--

ALTER SEQUENCE public.application_places_id_seq OWNED BY public.application_places.id;


--
-- Name: benefits; Type: TABLE; Schema: public; Owner: -
--

CREATE TABLE public.benefits (
    id integer NOT NULL,
    name character varying(100) NOT NULL,
    description text,
    category public.benefit_category,
    evidence_level public.evidence_level DEFAULT 'preliminary'::public.evidence_level,
    timeframe character varying(100),
    color_bg character varying(7),
    color_text character varying(7),
    icon text,
    sort_order integer DEFAULT 0 NOT NULL,
    is_active boolean DEFAULT true NOT NULL,
    deleted_at timestamp with time zone,
    created_at timestamp with time zone DEFAULT now(),
    updated_at timestamp with time zone DEFAULT now(),
    CONSTRAINT benefits_name_not_empty CHECK ((length(TRIM(BOTH FROM name)) > 0))
);


--
-- Name: benefits_id_seq; Type: SEQUENCE; Schema: public; Owner: -
--

CREATE SEQUENCE public.benefits_id_seq
    AS integer
    START WITH 1
    INCREMENT BY 1
    NO MINVALUE
    NO MAXVALUE
    CACHE 1;


--
-- Name: benefits_id_seq; Type: SEQUENCE OWNED BY; Schema: public; Owner: -
--

ALTER SEQUENCE public.benefits_id_seq OWNED BY public.benefits.id;


--
-- Name: calc_analytics; Type: TABLE; Schema: public; Owner: -
--

CREATE TABLE public.calc_analytics (
    id integer NOT NULL,
    ip_address character varying(45) NOT NULL,
    device_uuid character varying(64),
    action character varying(50) NOT NULL,
    peptide_id integer,
    page_url text,
    user_agent text,
    "timestamp" timestamp with time zone DEFAULT now() NOT NULL
);


--
-- Name: calc_analytics_id_seq; Type: SEQUENCE; Schema: public; Owner: -
--

CREATE SEQUENCE public.calc_analytics_id_seq
    AS integer
    START WITH 1
    INCREMENT BY 1
    NO MINVALUE
    NO MAXVALUE
    CACHE 1;


--
-- Name: calc_analytics_id_seq; Type: SEQUENCE OWNED BY; Schema: public; Owner: -
--

ALTER SEQUENCE public.calc_analytics_id_seq OWNED BY public.calc_analytics.id;


--
-- Name: calc_daily_stats; Type: TABLE; Schema: public; Owner: -
--

CREATE TABLE public.calc_daily_stats (
    id integer NOT NULL,
    device_uuid character varying(64) NOT NULL,
    date date NOT NULL,
    calculations integer DEFAULT 0,
    vial_views integer DEFAULT 0,
    profile_updates integer DEFAULT 0,
    created_at timestamp with time zone DEFAULT now(),
    CONSTRAINT calc_daily_stats_calculations_check CHECK ((calculations >= 0)),
    CONSTRAINT calc_daily_stats_vial_views_check CHECK ((vial_views >= 0))
);


--
-- Name: calc_daily_stats_id_seq; Type: SEQUENCE; Schema: public; Owner: -
--

CREATE SEQUENCE public.calc_daily_stats_id_seq
    AS integer
    START WITH 1
    INCREMENT BY 1
    NO MINVALUE
    NO MAXVALUE
    CACHE 1;


--
-- Name: calc_daily_stats_id_seq; Type: SEQUENCE OWNED BY; Schema: public; Owner: -
--

ALTER SEQUENCE public.calc_daily_stats_id_seq OWNED BY public.calc_daily_stats.id;


--
-- Name: calc_notification_devices; Type: TABLE; Schema: public; Owner: -
--

CREATE TABLE public.calc_notification_devices (
    id uuid DEFAULT gen_random_uuid() NOT NULL,
    notification_id uuid NOT NULL,
    user_device_id uuid NOT NULL,
    delivery_status public.delivery_status DEFAULT 'pending'::public.delivery_status NOT NULL,
    sent_at timestamp with time zone,
    delivered_at timestamp with time zone,
    failed_at timestamp with time zone,
    error_message text,
    retry_count integer DEFAULT 0,
    created_at timestamp with time zone DEFAULT now(),
    updated_at timestamp with time zone DEFAULT now(),
    CONSTRAINT calc_notification_devices_retry_count_check CHECK ((retry_count >= 0))
);


--
-- Name: calc_notifications; Type: TABLE; Schema: public; Owner: -
--

CREATE TABLE public.calc_notifications (
    id uuid DEFAULT gen_random_uuid() NOT NULL,
    user_id uuid,
    title character varying(255) NOT NULL,
    body text NOT NULL,
    scheduled_at timestamp with time zone,
    created_at timestamp with time zone DEFAULT now(),
    resend_count integer DEFAULT 0,
    last_resent_at timestamp with time zone,
    delivery_status public.delivery_status DEFAULT 'pending'::public.delivery_status NOT NULL
);


--
-- Name: calc_promo_banners; Type: TABLE; Schema: public; Owner: -
--

CREATE TABLE public.calc_promo_banners (
    id uuid DEFAULT gen_random_uuid() NOT NULL,
    is_visible boolean DEFAULT true NOT NULL,
    is_active boolean DEFAULT true NOT NULL,
    title character varying(100),
    code character varying(100) NOT NULL,
    description text NOT NULL,
    icon text,
    store_url text NOT NULL,
    button_text character varying(50) DEFAULT 'Shop Now'::character varying,
    days_left integer NOT NULL,
    hours_left integer NOT NULL,
    expires_at timestamp with time zone,
    theme_config jsonb,
    banner_type character varying(50),
    priority integer DEFAULT 0,
    start_date timestamp with time zone,
    end_date timestamp with time zone,
    click_count integer DEFAULT 0,
    view_count integer DEFAULT 0,
    created_by uuid,
    created_at timestamp with time zone DEFAULT now(),
    updated_at timestamp with time zone DEFAULT now(),
    CONSTRAINT calc_promo_banners_click_count_check CHECK ((click_count >= 0)),
    CONSTRAINT calc_promo_banners_days_left_check CHECK ((days_left >= 0)),
    CONSTRAINT calc_promo_banners_hours_left_check CHECK (((hours_left >= 0) AND (hours_left <= 23))),
    CONSTRAINT calc_promo_banners_priority_check CHECK ((priority >= 0)),
    CONSTRAINT calc_promo_banners_view_count_check CHECK ((view_count >= 0))
);


--
-- Name: calc_user_devices; Type: TABLE; Schema: public; Owner: -
--

CREATE TABLE public.calc_user_devices (
    id uuid DEFAULT gen_random_uuid() NOT NULL,
    user_id uuid NOT NULL,
    device_id character varying(255) NOT NULL,
    expo_push_token character varying(255),
    platform character varying(50) NOT NULL,
    device_model character varying(100),
    app_version character varying(20),
    locale character varying(10),
    timezone character varying(50),
    is_active boolean DEFAULT true,
    last_seen timestamp with time zone DEFAULT now(),
    created_at timestamp with time zone DEFAULT now(),
    updated_at timestamp with time zone DEFAULT now()
);


--
-- Name: calc_user_profiles; Type: TABLE; Schema: public; Owner: -
--

CREATE TABLE public.calc_user_profiles (
    id integer NOT NULL,
    user_id uuid NOT NULL,
    terms_accepted boolean DEFAULT false NOT NULL,
    terms_accepted_at timestamp with time zone,
    terms_version character varying(20),
    preferences jsonb,
    created_at timestamp with time zone DEFAULT now(),
    updated_at timestamp with time zone DEFAULT now(),
    CONSTRAINT calc_user_profiles_preferences_is_object CHECK (((preferences IS NULL) OR (jsonb_typeof(preferences) = 'object'::text)))
);


--
-- Name: calc_user_profiles_id_seq; Type: SEQUENCE; Schema: public; Owner: -
--

CREATE SEQUENCE public.calc_user_profiles_id_seq
    AS integer
    START WITH 1
    INCREMENT BY 1
    NO MINVALUE
    NO MAXVALUE
    CACHE 1;


--
-- Name: calc_user_profiles_id_seq; Type: SEQUENCE OWNED BY; Schema: public; Owner: -
--

ALTER SEQUENCE public.calc_user_profiles_id_seq OWNED BY public.calc_user_profiles.id;


--
-- Name: calc_user_reviews; Type: TABLE; Schema: public; Owner: -
--

CREATE TABLE public.calc_user_reviews (
    id integer NOT NULL,
    user_id uuid NOT NULL,
    rating integer NOT NULL,
    review_text text,
    is_active boolean DEFAULT true NOT NULL,
    created_at timestamp with time zone DEFAULT now(),
    updated_at timestamp with time zone DEFAULT now(),
    CONSTRAINT calc_user_reviews_rating_check CHECK (((rating >= 1) AND (rating <= 5)))
);


--
-- Name: calc_user_reviews_id_seq; Type: SEQUENCE; Schema: public; Owner: -
--

CREATE SEQUENCE public.calc_user_reviews_id_seq
    AS integer
    START WITH 1
    INCREMENT BY 1
    NO MINVALUE
    NO MAXVALUE
    CACHE 1;


--
-- Name: calc_user_reviews_id_seq; Type: SEQUENCE OWNED BY; Schema: public; Owner: -
--

ALTER SEQUENCE public.calc_user_reviews_id_seq OWNED BY public.calc_user_reviews.id;


--
-- Name: calc_vials; Type: TABLE; Schema: public; Owner: -
--

CREATE TABLE public.calc_vials (
    id uuid DEFAULT gen_random_uuid() NOT NULL,
    user_id uuid NOT NULL,
    peptide_name character varying(255) NOT NULL,
    syringe_size character varying(50) NOT NULL,
    unit character varying(20) NOT NULL,
    dose_unit character varying(20) NOT NULL,
    peptide_amount numeric(10,4) NOT NULL,
    bac_water numeric(10,4) NOT NULL,
    desired_amount numeric(10,4) NOT NULL,
    calculated_output text,
    peptide_amount_unit character varying(10) DEFAULT 'mg'::character varying,
    is_active boolean DEFAULT true NOT NULL,
    deleted_at timestamp with time zone,
    created_at timestamp with time zone DEFAULT now(),
    updated_at timestamp with time zone DEFAULT now(),
    CONSTRAINT calc_vials_bac_water_positive CHECK ((bac_water > (0)::numeric)),
    CONSTRAINT calc_vials_desired_amount_positive CHECK ((desired_amount > (0)::numeric)),
    CONSTRAINT calc_vials_peptide_amount_positive CHECK ((peptide_amount > (0)::numeric))
);


--
-- Name: categories; Type: TABLE; Schema: public; Owner: -
--

CREATE TABLE public.categories (
    id integer NOT NULL,
    parent_category_id integer,
    category_name character varying(100) NOT NULL,
    slug character varying(255) NOT NULL,
    color_bg character varying(7),
    color_text character varying(7),
    icon text,
    deleted_at timestamp with time zone,
    created_at timestamp with time zone DEFAULT now(),
    updated_at timestamp with time zone DEFAULT now(),
    CONSTRAINT categories_name_not_empty CHECK ((length(TRIM(BOTH FROM category_name)) > 0)),
    CONSTRAINT categories_not_self_parent CHECK (((parent_category_id IS NULL) OR (parent_category_id <> id))),
    CONSTRAINT categories_slug_not_empty CHECK ((length(TRIM(BOTH FROM slug)) > 0))
);


--
-- Name: categories_id_seq; Type: SEQUENCE; Schema: public; Owner: -
--

CREATE SEQUENCE public.categories_id_seq
    AS integer
    START WITH 1
    INCREMENT BY 1
    NO MINVALUE
    NO MAXVALUE
    CACHE 1;


--
-- Name: categories_id_seq; Type: SEQUENCE OWNED BY; Schema: public; Owner: -
--

ALTER SEQUENCE public.categories_id_seq OWNED BY public.categories.id;


--
-- Name: citations; Type: TABLE; Schema: public; Owner: -
--

CREATE TABLE public.citations (
    id integer NOT NULL,
    title character varying(500) NOT NULL,
    doi character varying(255) NOT NULL,
    publication_url text,
    authors text,
    journal character varying(255),
    publication_year integer,
    abstract text,
    created_at timestamp with time zone DEFAULT now(),
    updated_at timestamp with time zone DEFAULT now()
);


--
-- Name: citations_id_seq; Type: SEQUENCE; Schema: public; Owner: -
--

CREATE SEQUENCE public.citations_id_seq
    AS integer
    START WITH 1
    INCREMENT BY 1
    NO MINVALUE
    NO MAXVALUE
    CACHE 1;


--
-- Name: citations_id_seq; Type: SEQUENCE OWNED BY; Schema: public; Owner: -
--

ALTER SEQUENCE public.citations_id_seq OWNED BY public.citations.id;


--
-- Name: credit_accounts; Type: TABLE; Schema: public; Owner: -
--

CREATE TABLE public.credit_accounts (
    id uuid DEFAULT gen_random_uuid() NOT NULL,
    user_id uuid NOT NULL,
    balance integer DEFAULT 0 NOT NULL,
    lifetime_credits_purchased integer DEFAULT 0 NOT NULL,
    created_at timestamp with time zone DEFAULT now(),
    updated_at timestamp with time zone DEFAULT now(),
    CONSTRAINT credit_accounts_balance_non_negative CHECK ((balance >= 0)),
    CONSTRAINT credit_accounts_lifetime_non_negative CHECK ((lifetime_credits_purchased >= 0))
);


--
-- Name: credit_packages; Type: TABLE; Schema: public; Owner: -
--

CREATE TABLE public.credit_packages (
    id uuid DEFAULT gen_random_uuid() NOT NULL,
    name character varying(100) NOT NULL,
    credits integer NOT NULL,
    price_usd_cents integer NOT NULL,
    stripe_price_id character varying(255) NOT NULL,
    is_active boolean DEFAULT true NOT NULL,
    created_at timestamp with time zone DEFAULT now(),
    updated_at timestamp with time zone DEFAULT now(),
    sort_order integer DEFAULT 0 NOT NULL,
    app_source character varying(50),
    CONSTRAINT credit_packages_credits_positive CHECK ((credits > 0)),
    CONSTRAINT credit_packages_price_positive CHECK ((price_usd_cents > 0))
);


--
-- Name: credit_transactions; Type: TABLE; Schema: public; Owner: -
--

CREATE TABLE public.credit_transactions (
    id uuid DEFAULT gen_random_uuid() NOT NULL,
    user_id uuid NOT NULL,
    type public.credit_transaction_type NOT NULL,
    amount integer NOT NULL,
    balance_after integer NOT NULL,
    description text,
    reference_id character varying(255),
    created_at timestamp with time zone DEFAULT now(),
    credit_package_id uuid,
    metadata jsonb,
    app_source character varying(50),
    credit_account_id uuid,
    CONSTRAINT credit_transactions_amount_nonzero CHECK ((amount <> 0))
);


--
-- Name: dosages; Type: TABLE; Schema: public; Owner: -
--

CREATE TABLE public.dosages (
    id integer NOT NULL,
    name character varying(100) NOT NULL,
    amount numeric(10,4) NOT NULL,
    unit character varying(20) NOT NULL,
    description text,
    severity_level public.severity_level DEFAULT 'medium'::public.severity_level,
    color_bg character varying(7),
    color_text character varying(7),
    icon text,
    sort_order integer DEFAULT 0 NOT NULL,
    is_active boolean DEFAULT true NOT NULL,
    deleted_at timestamp with time zone,
    created_at timestamp with time zone DEFAULT now(),
    updated_at timestamp with time zone DEFAULT now(),
    CONSTRAINT dosages_amount_positive CHECK ((amount > (0)::numeric)),
    CONSTRAINT dosages_name_not_empty CHECK ((length(TRIM(BOTH FROM name)) > 0)),
    CONSTRAINT dosages_unit_not_empty CHECK ((length(TRIM(BOTH FROM unit)) > 0))
);


--
-- Name: dosages_id_seq; Type: SEQUENCE; Schema: public; Owner: -
--

CREATE SEQUENCE public.dosages_id_seq
    AS integer
    START WITH 1
    INCREMENT BY 1
    NO MINVALUE
    NO MAXVALUE
    CACHE 1;


--
-- Name: dosages_id_seq; Type: SEQUENCE OWNED BY; Schema: public; Owner: -
--

ALTER SEQUENCE public.dosages_id_seq OWNED BY public.dosages.id;


--
-- Name: feedback_questions; Type: TABLE; Schema: public; Owner: -
--

CREATE TABLE public.feedback_questions (
    id integer NOT NULL,
    question_code character varying(100) NOT NULL,
    question_label character varying(255) NOT NULL,
    question_type character varying(50) NOT NULL,
    sort_order integer DEFAULT 0 NOT NULL,
    is_active boolean DEFAULT true NOT NULL,
    created_at timestamp with time zone DEFAULT now(),
    updated_at timestamp with time zone DEFAULT now(),
    deleted_at timestamp with time zone
);


--
-- Name: feedback_questions_id_seq; Type: SEQUENCE; Schema: public; Owner: -
--

CREATE SEQUENCE public.feedback_questions_id_seq
    AS integer
    START WITH 1
    INCREMENT BY 1
    NO MINVALUE
    NO MAXVALUE
    CACHE 1;


--
-- Name: feedback_questions_id_seq; Type: SEQUENCE OWNED BY; Schema: public; Owner: -
--

ALTER SEQUENCE public.feedback_questions_id_seq OWNED BY public.feedback_questions.id;


--
-- Name: influencer_profiles; Type: TABLE; Schema: public; Owner: -
--

CREATE TABLE public.influencer_profiles (
    id integer NOT NULL,
    user_id uuid NOT NULL,
    display_name character varying(100),
    bio text,
    social_links jsonb,
    referral_code character varying(50),
    is_active boolean DEFAULT true NOT NULL,
    profile_visibility character varying(20) DEFAULT 'public'::character varying NOT NULL,
    created_at timestamp with time zone DEFAULT now() NOT NULL,
    updated_at timestamp with time zone DEFAULT now() NOT NULL
);


--
-- Name: influencer_profiles_id_seq; Type: SEQUENCE; Schema: public; Owner: -
--

CREATE SEQUENCE public.influencer_profiles_id_seq
    AS integer
    START WITH 1
    INCREMENT BY 1
    NO MINVALUE
    NO MAXVALUE
    CACHE 1;


--
-- Name: influencer_profiles_id_seq; Type: SEQUENCE OWNED BY; Schema: public; Owner: -
--

ALTER SEQUENCE public.influencer_profiles_id_seq OWNED BY public.influencer_profiles.id;


--
-- Name: pepti_price_analytics; Type: TABLE; Schema: public; Owner: -
--

CREATE TABLE public.pepti_price_analytics (
    id integer NOT NULL,
    ip_address character varying(45) NOT NULL,
    action character varying(50) NOT NULL,
    peptide_id integer,
    vendor_id integer,
    promo_code_id integer,
    page_url text,
    user_agent text,
    "timestamp" timestamp with time zone DEFAULT now() NOT NULL
);


--
-- Name: pepti_price_analytics_id_seq; Type: SEQUENCE; Schema: public; Owner: -
--

CREATE SEQUENCE public.pepti_price_analytics_id_seq
    AS integer
    START WITH 1
    INCREMENT BY 1
    NO MINVALUE
    NO MAXVALUE
    CACHE 1;


--
-- Name: pepti_price_analytics_id_seq; Type: SEQUENCE OWNED BY; Schema: public; Owner: -
--

ALTER SEQUENCE public.pepti_price_analytics_id_seq OWNED BY public.pepti_price_analytics.id;


--
-- Name: pepti_price_daily_stats; Type: TABLE; Schema: public; Owner: -
--

CREATE TABLE public.pepti_price_daily_stats (
    id integer NOT NULL,
    peptide_id integer NOT NULL,
    date date NOT NULL,
    price_comparisons integer DEFAULT 0,
    vendor_clicks integer DEFAULT 0,
    promo_applied integer DEFAULT 0,
    created_at timestamp with time zone DEFAULT now(),
    CONSTRAINT pepti_price_daily_stats_comparisons_check CHECK ((price_comparisons >= 0)),
    CONSTRAINT pepti_price_daily_stats_vendor_clicks_check CHECK ((vendor_clicks >= 0))
);


--
-- Name: pepti_price_daily_stats_id_seq; Type: SEQUENCE; Schema: public; Owner: -
--

CREATE SEQUENCE public.pepti_price_daily_stats_id_seq
    AS integer
    START WITH 1
    INCREMENT BY 1
    NO MINVALUE
    NO MAXVALUE
    CACHE 1;


--
-- Name: pepti_price_daily_stats_id_seq; Type: SEQUENCE OWNED BY; Schema: public; Owner: -
--

ALTER SEQUENCE public.pepti_price_daily_stats_id_seq OWNED BY public.pepti_price_daily_stats.id;


--
-- Name: pepti_price_newsletter_subscribers; Type: TABLE; Schema: public; Owner: -
--

CREATE TABLE public.pepti_price_newsletter_subscribers (
    id integer NOT NULL,
    email character varying(320) NOT NULL,
    source character varying(64),
    unsubscribe_token character varying(64) NOT NULL,
    confirmed_at timestamp with time zone,
    unsubscribed_at timestamp with time zone,
    created_at timestamp with time zone DEFAULT now() NOT NULL
);


--
-- Name: pepti_price_newsletter_subscribers_id_seq; Type: SEQUENCE; Schema: public; Owner: -
--

CREATE SEQUENCE public.pepti_price_newsletter_subscribers_id_seq
    AS integer
    START WITH 1
    INCREMENT BY 1
    NO MINVALUE
    NO MAXVALUE
    CACHE 1;


--
-- Name: pepti_price_newsletter_subscribers_id_seq; Type: SEQUENCE OWNED BY; Schema: public; Owner: -
--

ALTER SEQUENCE public.pepti_price_newsletter_subscribers_id_seq OWNED BY public.pepti_price_newsletter_subscribers.id;


--
-- Name: pepti_price_notifications; Type: TABLE; Schema: public; Owner: -
--

CREATE TABLE public.pepti_price_notifications (
    id integer NOT NULL,
    user_id uuid NOT NULL,
    type character varying(32) NOT NULL,
    payload jsonb DEFAULT '{}'::jsonb NOT NULL,
    read_at timestamp with time zone,
    created_at timestamp with time zone DEFAULT now() NOT NULL
);


--
-- Name: pepti_price_notifications_id_seq; Type: SEQUENCE; Schema: public; Owner: -
--

CREATE SEQUENCE public.pepti_price_notifications_id_seq
    AS integer
    START WITH 1
    INCREMENT BY 1
    NO MINVALUE
    NO MAXVALUE
    CACHE 1;


--
-- Name: pepti_price_notifications_id_seq; Type: SEQUENCE OWNED BY; Schema: public; Owner: -
--

ALTER SEQUENCE public.pepti_price_notifications_id_seq OWNED BY public.pepti_price_notifications.id;


--
-- Name: pepti_price_price_history; Type: TABLE; Schema: public; Owner: -
--

CREATE TABLE public.pepti_price_price_history (
    id integer NOT NULL,
    peptide_id integer NOT NULL,
    vendor_id integer NOT NULL,
    administration_method_id integer NOT NULL,
    dosage_value character varying(50) NOT NULL,
    dosage_id integer,
    original_price_per_mg numeric(10,2),
    original_total_price numeric(10,2),
    status public.stock_status DEFAULT 'in_stock'::public.stock_status NOT NULL,
    recorded_at timestamp with time zone DEFAULT now() NOT NULL
);


--
-- Name: pepti_price_price_history_id_seq; Type: SEQUENCE; Schema: public; Owner: -
--

CREATE SEQUENCE public.pepti_price_price_history_id_seq
    AS integer
    START WITH 1
    INCREMENT BY 1
    NO MINVALUE
    NO MAXVALUE
    CACHE 1;


--
-- Name: pepti_price_price_history_id_seq; Type: SEQUENCE OWNED BY; Schema: public; Owner: -
--

ALTER SEQUENCE public.pepti_price_price_history_id_seq OWNED BY public.pepti_price_price_history.id;


--
-- Name: pepti_price_promo_codes; Type: TABLE; Schema: public; Owner: -
--

CREATE TABLE public.pepti_price_promo_codes (
    id integer NOT NULL,
    code character varying(100) NOT NULL,
    discount_percentage integer DEFAULT 0 NOT NULL,
    start_time timestamp with time zone,
    end_time timestamp with time zone,
    is_active boolean DEFAULT true NOT NULL,
    created_at timestamp with time zone DEFAULT now(),
    updated_at timestamp with time zone DEFAULT now(),
    CONSTRAINT pepti_price_promo_codes_code_not_empty CHECK ((length(TRIM(BOTH FROM code)) > 0)),
    CONSTRAINT pepti_price_promo_codes_discount_range CHECK (((discount_percentage >= 0) AND (discount_percentage <= 100)))
);


--
-- Name: pepti_price_promo_codes_id_seq; Type: SEQUENCE; Schema: public; Owner: -
--

CREATE SEQUENCE public.pepti_price_promo_codes_id_seq
    AS integer
    START WITH 1
    INCREMENT BY 1
    NO MINVALUE
    NO MAXVALUE
    CACHE 1;


--
-- Name: pepti_price_promo_codes_id_seq; Type: SEQUENCE OWNED BY; Schema: public; Owner: -
--

ALTER SEQUENCE public.pepti_price_promo_codes_id_seq OWNED BY public.pepti_price_promo_codes.id;


--
-- Name: pepti_price_vendor_pricing; Type: TABLE; Schema: public; Owner: -
--

CREATE TABLE public.pepti_price_vendor_pricing (
    id integer NOT NULL,
    peptide_id integer NOT NULL,
    vendor_id integer NOT NULL,
    administration_method_id integer NOT NULL,
    dosage_value character varying(50) NOT NULL,
    original_price_per_mg numeric(10,2),
    original_total_price numeric(10,2),
    status public.stock_status DEFAULT 'in_stock'::public.stock_status NOT NULL,
    created_at timestamp with time zone DEFAULT now(),
    updated_at timestamp with time zone DEFAULT now(),
    promo_code_id integer,
    dosage_id integer
);


--
-- Name: pepti_price_vendor_pricing_id_seq; Type: SEQUENCE; Schema: public; Owner: -
--

CREATE SEQUENCE public.pepti_price_vendor_pricing_id_seq
    AS integer
    START WITH 1
    INCREMENT BY 1
    NO MINVALUE
    NO MAXVALUE
    CACHE 1;


--
-- Name: pepti_price_vendor_pricing_id_seq; Type: SEQUENCE OWNED BY; Schema: public; Owner: -
--

ALTER SEQUENCE public.pepti_price_vendor_pricing_id_seq OWNED BY public.pepti_price_vendor_pricing.id;


--
-- Name: pepti_price_watchlist; Type: TABLE; Schema: public; Owner: -
--

CREATE TABLE public.pepti_price_watchlist (
    id integer NOT NULL,
    user_id uuid NOT NULL,
    peptide_id integer NOT NULL,
    created_at timestamp with time zone DEFAULT now() NOT NULL
);


--
-- Name: pepti_price_watchlist_id_seq; Type: SEQUENCE; Schema: public; Owner: -
--

CREATE SEQUENCE public.pepti_price_watchlist_id_seq
    AS integer
    START WITH 1
    INCREMENT BY 1
    NO MINVALUE
    NO MAXVALUE
    CACHE 1;


--
-- Name: pepti_price_watchlist_id_seq; Type: SEQUENCE OWNED BY; Schema: public; Owner: -
--

ALTER SEQUENCE public.pepti_price_watchlist_id_seq OWNED BY public.pepti_price_watchlist.id;


--
-- Name: peptide_benefits; Type: TABLE; Schema: public; Owner: -
--

CREATE TABLE public.peptide_benefits (
    id integer NOT NULL,
    peptide_id integer NOT NULL,
    benefit_id integer NOT NULL,
    general_potency character varying(20) DEFAULT 'moderate'::character varying,
    general_evidence_level character varying(20) DEFAULT 'preliminary'::character varying,
    sort_order integer DEFAULT 0 NOT NULL,
    is_active boolean DEFAULT true NOT NULL,
    created_at timestamp with time zone DEFAULT now(),
    updated_at timestamp with time zone DEFAULT now()
);


--
-- Name: peptide_benefits_id_seq; Type: SEQUENCE; Schema: public; Owner: -
--

CREATE SEQUENCE public.peptide_benefits_id_seq
    AS integer
    START WITH 1
    INCREMENT BY 1
    NO MINVALUE
    NO MAXVALUE
    CACHE 1;


--
-- Name: peptide_benefits_id_seq; Type: SEQUENCE OWNED BY; Schema: public; Owner: -
--

ALTER SEQUENCE public.peptide_benefits_id_seq OWNED BY public.peptide_benefits.id;


--
-- Name: peptide_interactions; Type: TABLE; Schema: public; Owner: -
--

CREATE TABLE public.peptide_interactions (
    id integer NOT NULL,
    peptide_id_1 integer NOT NULL,
    peptide_id_2 integer,
    peptide_name_2 character varying(255),
    interaction_type public.interaction_type NOT NULL,
    description text NOT NULL,
    created_at timestamp with time zone DEFAULT now(),
    updated_at timestamp with time zone DEFAULT now(),
    severity character varying(20) DEFAULT 'low'::character varying,
    recommendation text,
    CONSTRAINT peptide_interactions_different_check CHECK ((peptide_id_1 <> peptide_id_2))
);


--
-- Name: peptide_interactions_id_seq; Type: SEQUENCE; Schema: public; Owner: -
--

CREATE SEQUENCE public.peptide_interactions_id_seq
    AS integer
    START WITH 1
    INCREMENT BY 1
    NO MINVALUE
    NO MAXVALUE
    CACHE 1;


--
-- Name: peptide_interactions_id_seq; Type: SEQUENCE OWNED BY; Schema: public; Owner: -
--

ALTER SEQUENCE public.peptide_interactions_id_seq OWNED BY public.peptide_interactions.id;


--
-- Name: peptide_protocol_reconstitution_steps; Type: TABLE; Schema: public; Owner: -
--

CREATE TABLE public.peptide_protocol_reconstitution_steps (
    id integer NOT NULL,
    protocol_id integer NOT NULL,
    step_number integer NOT NULL,
    description text NOT NULL,
    created_at timestamp with time zone DEFAULT now(),
    updated_at timestamp with time zone DEFAULT now()
);


--
-- Name: peptide_protocol_reconstitution_steps_id_seq; Type: SEQUENCE; Schema: public; Owner: -
--

CREATE SEQUENCE public.peptide_protocol_reconstitution_steps_id_seq
    AS integer
    START WITH 1
    INCREMENT BY 1
    NO MINVALUE
    NO MAXVALUE
    CACHE 1;


--
-- Name: peptide_protocol_reconstitution_steps_id_seq; Type: SEQUENCE OWNED BY; Schema: public; Owner: -
--

ALTER SEQUENCE public.peptide_protocol_reconstitution_steps_id_seq OWNED BY public.peptide_protocol_reconstitution_steps.id;


--
-- Name: peptide_protocols; Type: TABLE; Schema: public; Owner: -
--

CREATE TABLE public.peptide_protocols (
    id integer NOT NULL,
    peptide_id integer NOT NULL,
    administration_method_id integer NOT NULL,
    name character varying(100),
    description text,
    expectations jsonb,
    quick_start_guide jsonb,
    mechanism_of_action text,
    key_benefits text,
    best_timing character varying(200),
    effects_timeline character varying(200),
    is_recommended boolean DEFAULT false NOT NULL,
    sort_order integer DEFAULT 0 NOT NULL,
    is_active boolean DEFAULT true NOT NULL,
    deleted_at timestamp with time zone,
    created_at timestamp with time zone DEFAULT now(),
    updated_at timestamp with time zone DEFAULT now()
);


--
-- Name: peptide_protocols_id_seq; Type: SEQUENCE; Schema: public; Owner: -
--

CREATE SEQUENCE public.peptide_protocols_id_seq
    AS integer
    START WITH 1
    INCREMENT BY 1
    NO MINVALUE
    NO MAXVALUE
    CACHE 1;


--
-- Name: peptide_protocols_id_seq; Type: SEQUENCE OWNED BY; Schema: public; Owner: -
--

ALTER SEQUENCE public.peptide_protocols_id_seq OWNED BY public.peptide_protocols.id;


--
-- Name: peptide_question_assignments; Type: TABLE; Schema: public; Owner: -
--

CREATE TABLE public.peptide_question_assignments (
    id integer NOT NULL,
    peptide_id integer NOT NULL,
    question_id integer NOT NULL,
    sort_order integer DEFAULT 0 NOT NULL,
    is_active boolean DEFAULT true NOT NULL,
    created_at timestamp with time zone DEFAULT now(),
    updated_at timestamp with time zone DEFAULT now()
);


--
-- Name: peptide_question_assignments_id_seq; Type: SEQUENCE; Schema: public; Owner: -
--

CREATE SEQUENCE public.peptide_question_assignments_id_seq
    AS integer
    START WITH 1
    INCREMENT BY 1
    NO MINVALUE
    NO MAXVALUE
    CACHE 1;


--
-- Name: peptide_question_assignments_id_seq; Type: SEQUENCE OWNED BY; Schema: public; Owner: -
--

ALTER SEQUENCE public.peptide_question_assignments_id_seq OWNED BY public.peptide_question_assignments.id;


--
-- Name: peptide_question_option_assignments; Type: TABLE; Schema: public; Owner: -
--

CREATE TABLE public.peptide_question_option_assignments (
    id integer NOT NULL,
    question_id integer NOT NULL,
    question_option_id integer NOT NULL,
    sort_order integer DEFAULT 0 NOT NULL,
    is_active boolean DEFAULT true NOT NULL,
    created_at timestamp with time zone DEFAULT now(),
    updated_at timestamp with time zone DEFAULT now()
);


--
-- Name: peptide_question_option_assignments_id_seq; Type: SEQUENCE; Schema: public; Owner: -
--

CREATE SEQUENCE public.peptide_question_option_assignments_id_seq
    AS integer
    START WITH 1
    INCREMENT BY 1
    NO MINVALUE
    NO MAXVALUE
    CACHE 1;


--
-- Name: peptide_question_option_assignments_id_seq; Type: SEQUENCE OWNED BY; Schema: public; Owner: -
--

ALTER SEQUENCE public.peptide_question_option_assignments_id_seq OWNED BY public.peptide_question_option_assignments.id;


--
-- Name: peptide_question_options; Type: TABLE; Schema: public; Owner: -
--

CREATE TABLE public.peptide_question_options (
    id integer NOT NULL,
    option_text character varying(255) NOT NULL,
    created_at timestamp with time zone DEFAULT now(),
    updated_at timestamp with time zone DEFAULT now(),
    deleted_at timestamp with time zone
);


--
-- Name: peptide_question_options_id_seq; Type: SEQUENCE; Schema: public; Owner: -
--

CREATE SEQUENCE public.peptide_question_options_id_seq
    AS integer
    START WITH 1
    INCREMENT BY 1
    NO MINVALUE
    NO MAXVALUE
    CACHE 1;


--
-- Name: peptide_question_options_id_seq; Type: SEQUENCE OWNED BY; Schema: public; Owner: -
--

ALTER SEQUENCE public.peptide_question_options_id_seq OWNED BY public.peptide_question_options.id;


--
-- Name: peptide_questions; Type: TABLE; Schema: public; Owner: -
--

CREATE TABLE public.peptide_questions (
    id integer NOT NULL,
    question_text text NOT NULL,
    question_type character varying(50) NOT NULL,
    created_at timestamp with time zone DEFAULT now(),
    updated_at timestamp with time zone DEFAULT now(),
    deleted_at timestamp with time zone
);


--
-- Name: peptide_questions_id_seq; Type: SEQUENCE; Schema: public; Owner: -
--

CREATE SEQUENCE public.peptide_questions_id_seq
    AS integer
    START WITH 1
    INCREMENT BY 1
    NO MINVALUE
    NO MAXVALUE
    CACHE 1;


--
-- Name: peptide_questions_id_seq; Type: SEQUENCE OWNED BY; Schema: public; Owner: -
--

ALTER SEQUENCE public.peptide_questions_id_seq OWNED BY public.peptide_questions.id;


--
-- Name: peptide_references; Type: TABLE; Schema: public; Owner: -
--

CREATE TABLE public.peptide_references (
    id integer NOT NULL,
    peptide_id integer NOT NULL,
    reference_type public.reference_type NOT NULL,
    study_id integer,
    citation_id integer,
    context text,
    created_at timestamp with time zone DEFAULT now(),
    updated_at timestamp with time zone DEFAULT now(),
    CONSTRAINT peptide_references_type_check CHECK ((((reference_type = 'study'::public.reference_type) AND (study_id IS NOT NULL) AND (citation_id IS NULL)) OR ((reference_type = 'citation'::public.reference_type) AND (citation_id IS NOT NULL) AND (study_id IS NULL))))
);


--
-- Name: peptide_references_id_seq; Type: SEQUENCE; Schema: public; Owner: -
--

CREATE SEQUENCE public.peptide_references_id_seq
    AS integer
    START WITH 1
    INCREMENT BY 1
    NO MINVALUE
    NO MAXVALUE
    CACHE 1;


--
-- Name: peptide_references_id_seq; Type: SEQUENCE OWNED BY; Schema: public; Owner: -
--

ALTER SEQUENCE public.peptide_references_id_seq OWNED BY public.peptide_references.id;


--
-- Name: peptide_research_indication_studies; Type: TABLE; Schema: public; Owner: -
--

CREATE TABLE public.peptide_research_indication_studies (
    id integer NOT NULL,
    indication_id integer NOT NULL,
    protocol_id integer NOT NULL,
    study_title character varying(500) NOT NULL,
    study_description text,
    created_at timestamp with time zone DEFAULT now(),
    updated_at timestamp with time zone DEFAULT now()
);


--
-- Name: peptide_research_indication_studies_id_seq; Type: SEQUENCE; Schema: public; Owner: -
--

CREATE SEQUENCE public.peptide_research_indication_studies_id_seq
    AS integer
    START WITH 1
    INCREMENT BY 1
    NO MINVALUE
    NO MAXVALUE
    CACHE 1;


--
-- Name: peptide_research_indication_studies_id_seq; Type: SEQUENCE OWNED BY; Schema: public; Owner: -
--

ALTER SEQUENCE public.peptide_research_indication_studies_id_seq OWNED BY public.peptide_research_indication_studies.id;


--
-- Name: peptide_research_indications; Type: TABLE; Schema: public; Owner: -
--

CREATE TABLE public.peptide_research_indications (
    id integer NOT NULL,
    peptide_id integer NOT NULL,
    indication_title character varying(255) NOT NULL,
    effectiveness_tag public.effectiveness_tag DEFAULT 'moderate'::public.effectiveness_tag NOT NULL,
    created_at timestamp with time zone DEFAULT now(),
    updated_at timestamp with time zone DEFAULT now(),
    description text
);


--
-- Name: peptide_research_indications_id_seq; Type: SEQUENCE; Schema: public; Owner: -
--

CREATE SEQUENCE public.peptide_research_indications_id_seq
    AS integer
    START WITH 1
    INCREMENT BY 1
    NO MINVALUE
    NO MAXVALUE
    CACHE 1;


--
-- Name: peptide_research_indications_id_seq; Type: SEQUENCE OWNED BY; Schema: public; Owner: -
--

ALTER SEQUENCE public.peptide_research_indications_id_seq OWNED BY public.peptide_research_indications.id;


--
-- Name: peptide_side_effects; Type: TABLE; Schema: public; Owner: -
--

CREATE TABLE public.peptide_side_effects (
    id integer NOT NULL,
    peptide_id integer NOT NULL,
    side_effect_id integer NOT NULL,
    created_at timestamp with time zone DEFAULT now(),
    updated_at timestamp with time zone DEFAULT now()
);


--
-- Name: peptide_side_effects_id_seq; Type: SEQUENCE; Schema: public; Owner: -
--

CREATE SEQUENCE public.peptide_side_effects_id_seq
    AS integer
    START WITH 1
    INCREMENT BY 1
    NO MINVALUE
    NO MAXVALUE
    CACHE 1;


--
-- Name: peptide_side_effects_id_seq; Type: SEQUENCE OWNED BY; Schema: public; Owner: -
--

ALTER SEQUENCE public.peptide_side_effects_id_seq OWNED BY public.peptide_side_effects.id;


--
-- Name: peptides; Type: TABLE; Schema: public; Owner: -
--

CREATE TABLE public.peptides (
    id integer NOT NULL,
    slug character varying(255) NOT NULL,
    category_id integer,
    sequence character varying(1000),
    synonyms text,
    overview text,
    mechanism_of_action text,
    two_d_structure_photo text,
    iupac_name character varying(1000),
    molecular_mass character varying(200),
    molecular_formula character varying(200),
    potential_research_fields text,
    chemical_formula character varying(100),
    name character varying(255) NOT NULL,
    fda_approval_status public.fda_approval_status,
    wada_status public.wada_status,
    research_level public.research_level,
    chain_length integer,
    peptide_type public.peptide_type,
    modifications text,
    storage_temperature character varying(100),
    shelf_life_reconstituted character varying(100),
    cycle_duration character varying(100),
    break_period character varying(100),
    effect_onset character varying(100),
    required_materials text,
    safety_guidelines text,
    contraindications text,
    stop_signs text,
    quality_checks text,
    key_information text,
    is_popular boolean DEFAULT false NOT NULL,
    deleted_at timestamp with time zone,
    created_at timestamp with time zone DEFAULT now(),
    updated_at timestamp with time zone DEFAULT now(),
    half_life_value numeric(10,4),
    half_life_unit character varying(50),
    CONSTRAINT peptides_chain_length_check CHECK (((chain_length IS NULL) OR (chain_length > 0)))
);


--
-- Name: peptides_id_seq; Type: SEQUENCE; Schema: public; Owner: -
--

CREATE SEQUENCE public.peptides_id_seq
    AS integer
    START WITH 1
    INCREMENT BY 1
    NO MINVALUE
    NO MAXVALUE
    CACHE 1;


--
-- Name: peptides_id_seq; Type: SEQUENCE OWNED BY; Schema: public; Owner: -
--

ALTER SEQUENCE public.peptides_id_seq OWNED BY public.peptides.id;


--
-- Name: protocol_application_places; Type: TABLE; Schema: public; Owner: -
--

CREATE TABLE public.protocol_application_places (
    id integer NOT NULL,
    protocol_id integer NOT NULL,
    application_place_id integer NOT NULL,
    recommendation_level character varying(20) DEFAULT 'medium'::character varying,
    notes text,
    created_at timestamp with time zone DEFAULT now(),
    updated_at timestamp with time zone DEFAULT now()
);


--
-- Name: protocol_application_places_id_seq; Type: SEQUENCE; Schema: public; Owner: -
--

CREATE SEQUENCE public.protocol_application_places_id_seq
    AS integer
    START WITH 1
    INCREMENT BY 1
    NO MINVALUE
    NO MAXVALUE
    CACHE 1;


--
-- Name: protocol_application_places_id_seq; Type: SEQUENCE OWNED BY; Schema: public; Owner: -
--

ALTER SEQUENCE public.protocol_application_places_id_seq OWNED BY public.protocol_application_places.id;


--
-- Name: protocol_dosage_benefits; Type: TABLE; Schema: public; Owner: -
--

CREATE TABLE public.protocol_dosage_benefits (
    id integer NOT NULL,
    protocol_dosage_id integer NOT NULL,
    benefit_id integer NOT NULL,
    potency character varying(20) DEFAULT 'moderate'::character varying,
    onset_time character varying(50),
    peak_effect_time character varying(50),
    evidence_quality character varying(20) DEFAULT 'anecdotal'::character varying,
    citations text,
    notes text,
    sort_order integer DEFAULT 0 NOT NULL,
    is_active boolean DEFAULT true NOT NULL,
    created_at timestamp with time zone DEFAULT now(),
    updated_at timestamp with time zone DEFAULT now()
);


--
-- Name: protocol_dosage_benefits_id_seq; Type: SEQUENCE; Schema: public; Owner: -
--

CREATE SEQUENCE public.protocol_dosage_benefits_id_seq
    AS integer
    START WITH 1
    INCREMENT BY 1
    NO MINVALUE
    NO MAXVALUE
    CACHE 1;


--
-- Name: protocol_dosage_benefits_id_seq; Type: SEQUENCE OWNED BY; Schema: public; Owner: -
--

ALTER SEQUENCE public.protocol_dosage_benefits_id_seq OWNED BY public.protocol_dosage_benefits.id;


--
-- Name: protocol_dosage_side_effects; Type: TABLE; Schema: public; Owner: -
--

CREATE TABLE public.protocol_dosage_side_effects (
    id integer NOT NULL,
    protocol_dosage_id integer NOT NULL,
    side_effect_id integer NOT NULL,
    likelihood public.frequency DEFAULT 'uncommon'::public.frequency,
    notes text,
    created_at timestamp with time zone DEFAULT now(),
    updated_at timestamp with time zone DEFAULT now()
);


--
-- Name: protocol_dosage_side_effects_id_seq; Type: SEQUENCE; Schema: public; Owner: -
--

CREATE SEQUENCE public.protocol_dosage_side_effects_id_seq
    AS integer
    START WITH 1
    INCREMENT BY 1
    NO MINVALUE
    NO MAXVALUE
    CACHE 1;


--
-- Name: protocol_dosage_side_effects_id_seq; Type: SEQUENCE OWNED BY; Schema: public; Owner: -
--

ALTER SEQUENCE public.protocol_dosage_side_effects_id_seq OWNED BY public.protocol_dosage_side_effects.id;


--
-- Name: protocol_dosages; Type: TABLE; Schema: public; Owner: -
--

CREATE TABLE public.protocol_dosages (
    id integer NOT NULL,
    protocol_id integer NOT NULL,
    dosage_id integer NOT NULL,
    schedule_id integer NOT NULL,
    is_default boolean DEFAULT false NOT NULL,
    is_required boolean DEFAULT false NOT NULL,
    sort_order integer DEFAULT 0 NOT NULL,
    notes text,
    created_at timestamp with time zone DEFAULT now(),
    updated_at timestamp with time zone DEFAULT now()
);


--
-- Name: protocol_dosages_id_seq; Type: SEQUENCE; Schema: public; Owner: -
--

CREATE SEQUENCE public.protocol_dosages_id_seq
    AS integer
    START WITH 1
    INCREMENT BY 1
    NO MINVALUE
    NO MAXVALUE
    CACHE 1;


--
-- Name: protocol_dosages_id_seq; Type: SEQUENCE OWNED BY; Schema: public; Owner: -
--

ALTER SEQUENCE public.protocol_dosages_id_seq OWNED BY public.protocol_dosages.id;


--
-- Name: protocol_quality_indicators; Type: TABLE; Schema: public; Owner: -
--

CREATE TABLE public.protocol_quality_indicators (
    id integer NOT NULL,
    protocol_id integer NOT NULL,
    indicator_title character varying(255) NOT NULL,
    indicator_description text NOT NULL,
    sort_order integer DEFAULT 0 NOT NULL,
    created_at timestamp with time zone DEFAULT now(),
    updated_at timestamp with time zone DEFAULT now()
);


--
-- Name: protocol_quality_indicators_id_seq; Type: SEQUENCE; Schema: public; Owner: -
--

CREATE SEQUENCE public.protocol_quality_indicators_id_seq
    AS integer
    START WITH 1
    INCREMENT BY 1
    NO MINVALUE
    NO MAXVALUE
    CACHE 1;


--
-- Name: protocol_quality_indicators_id_seq; Type: SEQUENCE OWNED BY; Schema: public; Owner: -
--

ALTER SEQUENCE public.protocol_quality_indicators_id_seq OWNED BY public.protocol_quality_indicators.id;


--
-- Name: research_studies; Type: TABLE; Schema: public; Owner: -
--

CREATE TABLE public.research_studies (
    id integer NOT NULL,
    title character varying(500) NOT NULL,
    authors text,
    journal character varying(255),
    publication_year integer,
    abstract text,
    key_findings text,
    url text,
    tags text,
    created_at timestamp with time zone DEFAULT now(),
    updated_at timestamp with time zone DEFAULT now()
);


--
-- Name: research_studies_id_seq; Type: SEQUENCE; Schema: public; Owner: -
--

CREATE SEQUENCE public.research_studies_id_seq
    AS integer
    START WITH 1
    INCREMENT BY 1
    NO MINVALUE
    NO MAXVALUE
    CACHE 1;


--
-- Name: research_studies_id_seq; Type: SEQUENCE OWNED BY; Schema: public; Owner: -
--

ALTER SEQUENCE public.research_studies_id_seq OWNED BY public.research_studies.id;


--
-- Name: roles; Type: TABLE; Schema: public; Owner: -
--

CREATE TABLE public.roles (
    id integer NOT NULL,
    name character varying(50) NOT NULL,
    description text,
    permissions jsonb,
    is_system_role boolean DEFAULT false,
    created_at timestamp with time zone DEFAULT now(),
    updated_at timestamp with time zone DEFAULT now()
);


--
-- Name: roles_id_seq; Type: SEQUENCE; Schema: public; Owner: -
--

CREATE SEQUENCE public.roles_id_seq
    AS integer
    START WITH 1
    INCREMENT BY 1
    NO MINVALUE
    NO MAXVALUE
    CACHE 1;


--
-- Name: roles_id_seq; Type: SEQUENCE OWNED BY; Schema: public; Owner: -
--

ALTER SEQUENCE public.roles_id_seq OWNED BY public.roles.id;


--
-- Name: schedules; Type: TABLE; Schema: public; Owner: -
--

CREATE TABLE public.schedules (
    id integer NOT NULL,
    name character varying(100) NOT NULL,
    frequency character varying(100) NOT NULL,
    timing character varying(255),
    duration character varying(100),
    instructions text,
    color_bg character varying(7),
    color_text character varying(7),
    icon text,
    sort_order integer DEFAULT 0 NOT NULL,
    is_active boolean DEFAULT true NOT NULL,
    deleted_at timestamp with time zone,
    created_at timestamp with time zone DEFAULT now(),
    updated_at timestamp with time zone DEFAULT now(),
    CONSTRAINT schedules_duration_not_empty CHECK (((duration IS NULL) OR (length(TRIM(BOTH FROM duration)) > 0))),
    CONSTRAINT schedules_frequency_not_empty CHECK ((length(TRIM(BOTH FROM frequency)) > 0)),
    CONSTRAINT schedules_name_not_empty CHECK ((length(TRIM(BOTH FROM name)) > 0))
);


--
-- Name: schedules_id_seq; Type: SEQUENCE; Schema: public; Owner: -
--

CREATE SEQUENCE public.schedules_id_seq
    AS integer
    START WITH 1
    INCREMENT BY 1
    NO MINVALUE
    NO MAXVALUE
    CACHE 1;


--
-- Name: schedules_id_seq; Type: SEQUENCE OWNED BY; Schema: public; Owner: -
--

ALTER SEQUENCE public.schedules_id_seq OWNED BY public.schedules.id;


--
-- Name: sds_analytics; Type: TABLE; Schema: public; Owner: -
--

CREATE TABLE public.sds_analytics (
    id integer NOT NULL,
    ip_address character varying(45) NOT NULL,
    action character varying(50) NOT NULL,
    compound_id integer,
    document_id integer,
    page_url text,
    user_agent text,
    "timestamp" timestamp with time zone DEFAULT now() NOT NULL,
    CONSTRAINT sds_analytics_compound_id_check CHECK (((compound_id IS NULL) OR (compound_id > 0))),
    CONSTRAINT sds_analytics_document_id_check CHECK (((document_id IS NULL) OR (document_id > 0)))
);


--
-- Name: sds_analytics_id_seq; Type: SEQUENCE; Schema: public; Owner: -
--

CREATE SEQUENCE public.sds_analytics_id_seq
    AS integer
    START WITH 1
    INCREMENT BY 1
    NO MINVALUE
    NO MAXVALUE
    CACHE 1;


--
-- Name: sds_analytics_id_seq; Type: SEQUENCE OWNED BY; Schema: public; Owner: -
--

ALTER SEQUENCE public.sds_analytics_id_seq OWNED BY public.sds_analytics.id;


--
-- Name: sds_batches; Type: TABLE; Schema: public; Owner: -
--

CREATE TABLE public.sds_batches (
    id uuid DEFAULT gen_random_uuid() NOT NULL,
    status text NOT NULL,
    total integer NOT NULL,
    done integer DEFAULT 0 NOT NULL,
    failed integer DEFAULT 0 NOT NULL,
    user_email text,
    company_profile jsonb NOT NULL,
    template_config jsonb,
    watermark_text text,
    fields jsonb DEFAULT '{}'::jsonb NOT NULL,
    cids jsonb NOT NULL,
    compound_statuses jsonb DEFAULT '{}'::jsonb NOT NULL,
    document_ids jsonb DEFAULT '[]'::jsonb NOT NULL,
    created_at timestamp with time zone DEFAULT now() NOT NULL,
    completed_at timestamp with time zone
);


--
-- Name: sds_compounds; Type: TABLE; Schema: public; Owner: -
--

CREATE TABLE public.sds_compounds (
    id uuid DEFAULT gen_random_uuid() NOT NULL,
    peptide_id integer,
    name text NOT NULL,
    cas_number text,
    pubchem_cid bigint,
    iupac_name text,
    molecular_formula text,
    molecular_weight numeric,
    synonyms text[],
    smiles text,
    inchi_key text,
    inchi text,
    appearance text,
    odor text,
    boiling_point text,
    melting_point text,
    flash_point text,
    vapor_pressure text,
    vapor_density text,
    specific_gravity text,
    solubility text,
    ph text,
    fetch_status public.sds_fetch_status DEFAULT 'pending'::public.sds_fetch_status NOT NULL,
    last_fetched_at timestamp with time zone DEFAULT now(),
    created_at timestamp with time zone DEFAULT now(),
    deleted_at timestamp with time zone
);


--
-- Name: sds_documents; Type: TABLE; Schema: public; Owner: -
--

CREATE TABLE public.sds_documents (
    id uuid DEFAULT gen_random_uuid() NOT NULL,
    compound_id uuid,
    company_name text,
    company_address text,
    company_phone text,
    company_emergency_contact text,
    company_emergency_phone text,
    company_logo_url text,
    company_website text,
    pdf_url text,
    version integer DEFAULT 1,
    revision_date date DEFAULT now(),
    manual_overrides jsonb DEFAULT '{}'::jsonb,
    watermark_text text,
    generated_at timestamp with time zone DEFAULT now(),
    deleted_at timestamp with time zone,
    user_id uuid
);


--
-- Name: sds_hazard_data; Type: TABLE; Schema: public; Owner: -
--

CREATE TABLE public.sds_hazard_data (
    id uuid DEFAULT gen_random_uuid() NOT NULL,
    compound_id uuid NOT NULL,
    signal_word text,
    ghs_pictograms text[],
    hazard_statements text[],
    precautionary_statements text[],
    health_hazard text,
    flammability text,
    reactivity text,
    specific_hazards text,
    source text DEFAULT 'pubchem'::text,
    created_at timestamp with time zone DEFAULT now(),
    updated_at timestamp with time zone DEFAULT now(),
    deleted_at timestamp with time zone
);


--
-- Name: sds_job_queue; Type: TABLE; Schema: public; Owner: -
--

CREATE TABLE public.sds_job_queue (
    id uuid DEFAULT gen_random_uuid() NOT NULL,
    compound_id uuid,
    type text DEFAULT 'compound_fetch'::text NOT NULL,
    status text DEFAULT 'pending'::text NOT NULL,
    priority integer DEFAULT 0,
    payload jsonb NOT NULL,
    result jsonb,
    error text,
    attempts integer DEFAULT 0,
    max_attempts integer DEFAULT 3,
    created_at timestamp with time zone DEFAULT now(),
    updated_at timestamp with time zone DEFAULT now(),
    started_at timestamp with time zone,
    completed_at timestamp with time zone,
    user_id uuid,
    CONSTRAINT sds_job_queue_status_check CHECK ((status = ANY (ARRAY['pending'::text, 'processing'::text, 'completed'::text, 'failed'::text]))),
    CONSTRAINT sds_job_queue_type_check CHECK ((type = ANY (ARRAY['compound_fetch'::text, 'pdf_generation'::text])))
);


--
-- Name: sds_pdf_templates; Type: TABLE; Schema: public; Owner: -
--

CREATE TABLE public.sds_pdf_templates (
    id uuid DEFAULT gen_random_uuid() NOT NULL,
    name text NOT NULL,
    is_default boolean DEFAULT false,
    config jsonb NOT NULL,
    created_at timestamp with time zone DEFAULT now(),
    updated_at timestamp with time zone DEFAULT now(),
    deleted_at timestamp with time zone
);


--
-- Name: sds_pinned_compounds; Type: TABLE; Schema: public; Owner: -
--

CREATE TABLE public.sds_pinned_compounds (
    id uuid DEFAULT gen_random_uuid() NOT NULL,
    compound_id uuid,
    display_name text NOT NULL,
    pubchem_cid bigint,
    drugbank_id text,
    chembl_id text,
    cas_number text,
    molecular_formula text,
    category text DEFAULT 'Research'::text,
    verified boolean DEFAULT true,
    sort_order integer DEFAULT 0,
    created_at timestamp with time zone DEFAULT now(),
    deleted_at timestamp with time zone
);


--
-- Name: sds_sections; Type: TABLE; Schema: public; Owner: -
--

CREATE TABLE public.sds_sections (
    id uuid DEFAULT gen_random_uuid() NOT NULL,
    compound_id uuid NOT NULL,
    handling_precautions text,
    storage_conditions text,
    incompatibilities text,
    exposure_limits text,
    engineering_controls text,
    ppe_respiratory text,
    ppe_hands text,
    ppe_eyes text,
    ppe_skin text,
    acute_toxicity text,
    skin_corrosion text,
    eye_damage text,
    sensitization text,
    carcinogenicity text,
    reproductive_toxicity text,
    target_organ text,
    ecotoxicity text,
    persistence text,
    bioaccumulation text,
    section7_source text DEFAULT 'pubchem'::text,
    section8_source text DEFAULT 'pubchem'::text,
    section11_source text DEFAULT 'pubchem'::text,
    section12_source text DEFAULT 'pubchem'::text,
    created_at timestamp with time zone DEFAULT now(),
    updated_at timestamp with time zone DEFAULT now(),
    deleted_at timestamp with time zone
);


--
-- Name: side_effects; Type: TABLE; Schema: public; Owner: -
--

CREATE TABLE public.side_effects (
    id integer NOT NULL,
    name character varying(100) NOT NULL,
    description text,
    severity_level public.side_effect_severity DEFAULT 'mild'::public.side_effect_severity,
    frequency public.frequency DEFAULT 'uncommon'::public.frequency,
    category character varying(50),
    color_bg character varying(7),
    color_text character varying(7),
    icon text,
    sort_order integer DEFAULT 0 NOT NULL,
    is_active boolean DEFAULT true NOT NULL,
    deleted_at timestamp with time zone,
    created_at timestamp with time zone DEFAULT now(),
    updated_at timestamp with time zone DEFAULT now(),
    CONSTRAINT side_effects_name_not_empty CHECK ((length(TRIM(BOTH FROM name)) > 0))
);


--
-- Name: side_effects_id_seq; Type: SEQUENCE; Schema: public; Owner: -
--

CREATE SEQUENCE public.side_effects_id_seq
    AS integer
    START WITH 1
    INCREMENT BY 1
    NO MINVALUE
    NO MAXVALUE
    CACHE 1;


--
-- Name: side_effects_id_seq; Type: SEQUENCE OWNED BY; Schema: public; Owner: -
--

ALTER SEQUENCE public.side_effects_id_seq OWNED BY public.side_effects.id;


--
-- Name: stripe_customers; Type: TABLE; Schema: public; Owner: -
--

CREATE TABLE public.stripe_customers (
    id uuid DEFAULT gen_random_uuid() NOT NULL,
    user_id uuid NOT NULL,
    stripe_customer_id character varying(255) NOT NULL,
    created_at timestamp with time zone DEFAULT now(),
    updated_at timestamp with time zone DEFAULT now()
);


--
-- Name: subscription_events; Type: TABLE; Schema: public; Owner: -
--

CREATE TABLE public.subscription_events (
    id uuid DEFAULT gen_random_uuid() NOT NULL,
    stripe_event_id character varying(255) NOT NULL,
    event_type character varying(100) NOT NULL,
    subscription_id uuid,
    user_id uuid,
    stripe_subscription_id character varying(255),
    payload jsonb,
    previous_status text,
    new_status text,
    processed_at timestamp with time zone,
    processing_error text,
    created_at timestamp with time zone DEFAULT now(),
    source_type character varying(50),
    source_id character varying(255)
);


--
-- Name: subscriptions; Type: TABLE; Schema: public; Owner: -
--

CREATE TABLE public.subscriptions (
    id uuid DEFAULT gen_random_uuid() NOT NULL,
    user_id uuid NOT NULL,
    stripe_subscription_id character varying(255) NOT NULL,
    stripe_customer_id character varying(255) NOT NULL,
    stripe_product_id character varying(255),
    stripe_price_id character varying(255),
    status character varying(50) NOT NULL,
    cancel_at_period_end boolean DEFAULT false NOT NULL,
    current_period_start timestamp with time zone,
    current_period_end timestamp with time zone,
    canceled_at timestamp with time zone,
    trial_end timestamp with time zone,
    metadata text,
    created_at timestamp with time zone DEFAULT now(),
    updated_at timestamp with time zone DEFAULT now()
);


--
-- Name: user_roles; Type: TABLE; Schema: public; Owner: -
--

CREATE TABLE public.user_roles (
    id integer NOT NULL,
    user_id uuid NOT NULL,
    role_id integer NOT NULL,
    app_context character varying(50),
    granted_by uuid,
    granted_at timestamp with time zone DEFAULT now(),
    expires_at timestamp with time zone,
    is_active boolean DEFAULT true,
    created_at timestamp with time zone DEFAULT now()
);


--
-- Name: user_roles_id_seq; Type: SEQUENCE; Schema: public; Owner: -
--

CREATE SEQUENCE public.user_roles_id_seq
    AS integer
    START WITH 1
    INCREMENT BY 1
    NO MINVALUE
    NO MAXVALUE
    CACHE 1;


--
-- Name: user_roles_id_seq; Type: SEQUENCE OWNED BY; Schema: public; Owner: -
--

ALTER SEQUENCE public.user_roles_id_seq OWNED BY public.user_roles.id;


--
-- Name: user_suggestions; Type: TABLE; Schema: public; Owner: -
--

CREATE TABLE public.user_suggestions (
    id integer NOT NULL,
    email character varying(255) NOT NULL,
    user_id uuid,
    suggestion_text text NOT NULL,
    entity_type character varying(50),
    entity_name character varying(255),
    entity_slug character varying(255),
    page_url text,
    status public.suggestion_status DEFAULT 'pending'::public.suggestion_status NOT NULL,
    admin_notes text,
    reviewed_by uuid,
    reviewed_at timestamp with time zone,
    created_at timestamp with time zone DEFAULT now() NOT NULL,
    updated_at timestamp with time zone DEFAULT now() NOT NULL,
    app_source character varying(50) DEFAULT 'wiki'::character varying NOT NULL
);


--
-- Name: user_suggestions_id_seq; Type: SEQUENCE; Schema: public; Owner: -
--

CREATE SEQUENCE public.user_suggestions_id_seq
    AS integer
    START WITH 1
    INCREMENT BY 1
    NO MINVALUE
    NO MAXVALUE
    CACHE 1;


--
-- Name: user_suggestions_id_seq; Type: SEQUENCE OWNED BY; Schema: public; Owner: -
--

ALTER SEQUENCE public.user_suggestions_id_seq OWNED BY public.user_suggestions.id;


--
-- Name: users; Type: TABLE; Schema: public; Owner: -
--

CREATE TABLE public.users (
    id uuid DEFAULT gen_random_uuid() NOT NULL,
    auth_user_id character varying(255) NOT NULL,
    email character varying(255) NOT NULL,
    first_name character varying(255),
    last_name character varying(255),
    image_url text,
    phone character varying(50),
    is_active boolean DEFAULT true,
    email_verified boolean DEFAULT false,
    last_login_at timestamp with time zone,
    created_at timestamp with time zone DEFAULT now(),
    updated_at timestamp with time zone DEFAULT now(),
    deleted_at timestamp with time zone
);


--
-- Name: vendor_peptides; Type: TABLE; Schema: public; Owner: -
--

CREATE TABLE public.vendor_peptides (
    id integer NOT NULL,
    vendor_id integer NOT NULL,
    peptide_id integer NOT NULL,
    shopnow_link text,
    product_photo text,
    purity character varying(100),
    weight character varying(15),
    certificate_of_authenticity_link text,
    deleted_at timestamp with time zone,
    created_at timestamp with time zone DEFAULT now(),
    updated_at timestamp with time zone DEFAULT now(),
    CONSTRAINT vendor_peptides_purity_format CHECK (((purity IS NULL) OR ((purity)::text ~ '^[0-9]{1,3}(\.[0-9]{1,3})?%$'::text)))
);


--
-- Name: vendor_peptides_id_seq; Type: SEQUENCE; Schema: public; Owner: -
--

CREATE SEQUENCE public.vendor_peptides_id_seq
    AS integer
    START WITH 1
    INCREMENT BY 1
    NO MINVALUE
    NO MAXVALUE
    CACHE 1;


--
-- Name: vendor_peptides_id_seq; Type: SEQUENCE OWNED BY; Schema: public; Owner: -
--

ALTER SEQUENCE public.vendor_peptides_id_seq OWNED BY public.vendor_peptides.id;


--
-- Name: vendors; Type: TABLE; Schema: public; Owner: -
--

CREATE TABLE public.vendors (
    id integer NOT NULL,
    name character varying(255) DEFAULT 'Researchem'::character varying NOT NULL,
    slug character varying(255) NOT NULL,
    icon text,
    company_description text,
    affordability_rating numeric(3,2),
    quality_rating numeric(3,2),
    shipping_speed_rating numeric(3,2),
    customer_service_rating numeric(3,2),
    color_bg character varying(7),
    color_text character varying(7),
    promo_code_id integer,
    is_us_vendor boolean DEFAULT false NOT NULL,
    is_popular boolean DEFAULT false NOT NULL,
    deleted_at timestamp with time zone,
    created_at timestamp with time zone DEFAULT now(),
    updated_at timestamp with time zone DEFAULT now(),
    CONSTRAINT vendors_affordability_rating_range CHECK (((affordability_rating IS NULL) OR ((affordability_rating >= (0)::numeric) AND (affordability_rating <= (5)::numeric)))),
    CONSTRAINT vendors_name_not_empty CHECK ((length(TRIM(BOTH FROM name)) > 0)),
    CONSTRAINT vendors_quality_rating_range CHECK (((quality_rating IS NULL) OR ((quality_rating >= (0)::numeric) AND (quality_rating <= (5)::numeric)))),
    CONSTRAINT vendors_service_rating_range CHECK (((customer_service_rating IS NULL) OR ((customer_service_rating >= (0)::numeric) AND (customer_service_rating <= (5)::numeric)))),
    CONSTRAINT vendors_shipping_rating_range CHECK (((shipping_speed_rating IS NULL) OR ((shipping_speed_rating >= (0)::numeric) AND (shipping_speed_rating <= (5)::numeric)))),
    CONSTRAINT vendors_slug_not_empty CHECK ((length(TRIM(BOTH FROM slug)) > 0))
);


--
-- Name: vendors_id_seq; Type: SEQUENCE; Schema: public; Owner: -
--

CREATE SEQUENCE public.vendors_id_seq
    AS integer
    START WITH 1
    INCREMENT BY 1
    NO MINVALUE
    NO MAXVALUE
    CACHE 1;


--
-- Name: vendors_id_seq; Type: SEQUENCE OWNED BY; Schema: public; Owner: -
--

ALTER SEQUENCE public.vendors_id_seq OWNED BY public.vendors.id;


--
-- Name: wiki_copilot_settings; Type: TABLE; Schema: public; Owner: -
--

CREATE TABLE public.wiki_copilot_settings (
    key character varying(64) NOT NULL,
    value text NOT NULL,
    updated_at timestamp with time zone DEFAULT now() NOT NULL,
    updated_by character varying(255)
);


--
-- Name: wiki_coupons; Type: TABLE; Schema: public; Owner: -
--

CREATE TABLE public.wiki_coupons (
    id integer NOT NULL,
    code character varying(50) NOT NULL,
    vendor_id integer,
    influencer_id uuid,
    discount_type character varying(20) NOT NULL,
    discount_value numeric(10,2) NOT NULL,
    description text,
    start_date timestamp with time zone,
    end_date timestamp with time zone,
    is_active boolean DEFAULT true NOT NULL,
    usage_count integer DEFAULT 0,
    max_usage integer,
    affiliate_url text,
    deleted_at timestamp with time zone,
    created_at timestamp with time zone DEFAULT now(),
    updated_at timestamp with time zone DEFAULT now(),
    CONSTRAINT wiki_coupons_discount_value_check CHECK ((discount_value >= (0)::numeric)),
    CONSTRAINT wiki_coupons_max_usage_check CHECK (((max_usage IS NULL) OR (max_usage > 0))),
    CONSTRAINT wiki_coupons_usage_count_check CHECK ((usage_count >= 0))
);


--
-- Name: wiki_coupons_id_seq; Type: SEQUENCE; Schema: public; Owner: -
--

CREATE SEQUENCE public.wiki_coupons_id_seq
    AS integer
    START WITH 1
    INCREMENT BY 1
    NO MINVALUE
    NO MAXVALUE
    CACHE 1;


--
-- Name: wiki_coupons_id_seq; Type: SEQUENCE OWNED BY; Schema: public; Owner: -
--

ALTER SEQUENCE public.wiki_coupons_id_seq OWNED BY public.wiki_coupons.id;


--
-- Name: wiki_influencer_analytics; Type: TABLE; Schema: public; Owner: -
--

CREATE TABLE public.wiki_influencer_analytics (
    id integer NOT NULL,
    user_id uuid NOT NULL,
    page_views integer DEFAULT 0,
    clicks integer DEFAULT 0,
    clicks_vendors integer DEFAULT 0,
    created_at timestamp with time zone DEFAULT now(),
    updated_at timestamp with time zone DEFAULT now(),
    CONSTRAINT wiki_influencer_analytics_clicks_check CHECK ((clicks >= 0)),
    CONSTRAINT wiki_influencer_analytics_clicks_vendors_check CHECK ((clicks_vendors >= 0)),
    CONSTRAINT wiki_influencer_analytics_page_views_check CHECK ((page_views >= 0))
);


--
-- Name: wiki_influencer_analytics_id_seq; Type: SEQUENCE; Schema: public; Owner: -
--

CREATE SEQUENCE public.wiki_influencer_analytics_id_seq
    AS integer
    START WITH 1
    INCREMENT BY 1
    NO MINVALUE
    NO MAXVALUE
    CACHE 1;


--
-- Name: wiki_influencer_analytics_id_seq; Type: SEQUENCE OWNED BY; Schema: public; Owner: -
--

ALTER SEQUENCE public.wiki_influencer_analytics_id_seq OWNED BY public.wiki_influencer_analytics.id;


--
-- Name: wiki_peptide_analytics; Type: TABLE; Schema: public; Owner: -
--

CREATE TABLE public.wiki_peptide_analytics (
    id integer NOT NULL,
    ip_address character varying(45) NOT NULL,
    peptide_id integer NOT NULL,
    action character varying(50) NOT NULL,
    referer_url text,
    user_agent text,
    "timestamp" timestamp with time zone DEFAULT now() NOT NULL
);


--
-- Name: wiki_peptide_analytics_id_seq; Type: SEQUENCE; Schema: public; Owner: -
--

CREATE SEQUENCE public.wiki_peptide_analytics_id_seq
    AS integer
    START WITH 1
    INCREMENT BY 1
    NO MINVALUE
    NO MAXVALUE
    CACHE 1;


--
-- Name: wiki_peptide_analytics_id_seq; Type: SEQUENCE OWNED BY; Schema: public; Owner: -
--

ALTER SEQUENCE public.wiki_peptide_analytics_id_seq OWNED BY public.wiki_peptide_analytics.id;


--
-- Name: wiki_posts; Type: TABLE; Schema: public; Owner: -
--

CREATE TABLE public.wiki_posts (
    id integer NOT NULL,
    slug character varying(255) NOT NULL,
    title character varying(255) NOT NULL,
    content text NOT NULL,
    author_name character varying(255) NOT NULL,
    status character varying(20) DEFAULT 'draft'::character varying NOT NULL,
    published_at timestamp with time zone,
    categories text[],
    meta_title character varying(255),
    meta_description text,
    og_title character varying(255),
    og_description text,
    og_image character varying(500),
    canonical_url character varying(500),
    created_at timestamp with time zone DEFAULT now(),
    updated_at timestamp with time zone DEFAULT now()
);


--
-- Name: wiki_posts_id_seq; Type: SEQUENCE; Schema: public; Owner: -
--

CREATE SEQUENCE public.wiki_posts_id_seq
    AS integer
    START WITH 1
    INCREMENT BY 1
    NO MINVALUE
    NO MAXVALUE
    CACHE 1;


--
-- Name: wiki_posts_id_seq; Type: SEQUENCE OWNED BY; Schema: public; Owner: -
--

ALTER SEQUENCE public.wiki_posts_id_seq OWNED BY public.wiki_posts.id;


--
-- Name: wiki_referral_banners; Type: TABLE; Schema: public; Owner: -
--

CREATE TABLE public.wiki_referral_banners (
    id integer NOT NULL,
    user_id uuid NOT NULL,
    title character varying(255),
    description text,
    theme_config jsonb,
    social_links_config jsonb,
    custom_url text,
    avatar_url text,
    is_active boolean DEFAULT true,
    sort_order integer DEFAULT 0,
    created_at timestamp with time zone DEFAULT now(),
    updated_at timestamp with time zone DEFAULT now(),
    avatar_type character varying(20) DEFAULT 'initials'::character varying,
    avatar_icon text,
    CONSTRAINT wiki_referral_banners_sort_order_check CHECK ((sort_order >= 0))
);


--
-- Name: wiki_referral_banners_id_seq; Type: SEQUENCE; Schema: public; Owner: -
--

CREATE SEQUENCE public.wiki_referral_banners_id_seq
    AS integer
    START WITH 1
    INCREMENT BY 1
    NO MINVALUE
    NO MAXVALUE
    CACHE 1;


--
-- Name: wiki_referral_banners_id_seq; Type: SEQUENCE OWNED BY; Schema: public; Owner: -
--

ALTER SEQUENCE public.wiki_referral_banners_id_seq OWNED BY public.wiki_referral_banners.id;


--
-- Name: wiki_referral_clicks; Type: TABLE; Schema: public; Owner: -
--

CREATE TABLE public.wiki_referral_clicks (
    id integer NOT NULL,
    referral_code character varying(50) NOT NULL,
    user_id uuid NOT NULL,
    vendor_id integer,
    peptide_id integer,
    ip_address character varying(45),
    user_agent text,
    referer_url text,
    action character varying(50) NOT NULL,
    tracking_id character varying(100),
    social_source_url character varying(100),
    "timestamp" timestamp with time zone DEFAULT now()
);


--
-- Name: wiki_referral_clicks_id_seq; Type: SEQUENCE; Schema: public; Owner: -
--

CREATE SEQUENCE public.wiki_referral_clicks_id_seq
    AS integer
    START WITH 1
    INCREMENT BY 1
    NO MINVALUE
    NO MAXVALUE
    CACHE 1;


--
-- Name: wiki_referral_clicks_id_seq; Type: SEQUENCE OWNED BY; Schema: public; Owner: -
--

ALTER SEQUENCE public.wiki_referral_clicks_id_seq OWNED BY public.wiki_referral_clicks.id;


--
-- Name: wiki_trending_peptides; Type: TABLE; Schema: public; Owner: -
--

CREATE TABLE public.wiki_trending_peptides (
    id integer NOT NULL,
    peptide_id integer NOT NULL,
    views integer DEFAULT 0,
    clicks integer DEFAULT 0,
    shares integer DEFAULT 0,
    created_at timestamp with time zone DEFAULT now(),
    updated_at timestamp with time zone DEFAULT now(),
    CONSTRAINT wiki_trending_peptides_clicks_check CHECK ((clicks >= 0)),
    CONSTRAINT wiki_trending_peptides_shares_check CHECK ((shares >= 0)),
    CONSTRAINT wiki_trending_peptides_views_check CHECK ((views >= 0))
);


--
-- Name: wiki_trending_peptides_id_seq; Type: SEQUENCE; Schema: public; Owner: -
--

CREATE SEQUENCE public.wiki_trending_peptides_id_seq
    AS integer
    START WITH 1
    INCREMENT BY 1
    NO MINVALUE
    NO MAXVALUE
    CACHE 1;


--
-- Name: wiki_trending_peptides_id_seq; Type: SEQUENCE OWNED BY; Schema: public; Owner: -
--

ALTER SEQUENCE public.wiki_trending_peptides_id_seq OWNED BY public.wiki_trending_peptides.id;


--
-- Name: wiki_user_peptide_feedback_answers; Type: TABLE; Schema: public; Owner: -
--

CREATE TABLE public.wiki_user_peptide_feedback_answers (
    id integer NOT NULL,
    user_id uuid NOT NULL,
    peptide_id integer,
    feedback_question_id integer NOT NULL,
    response character varying(255) NOT NULL,
    answered_at timestamp with time zone DEFAULT now() NOT NULL,
    was_helpful boolean
);


--
-- Name: wiki_user_peptide_feedback_answers_id_seq; Type: SEQUENCE; Schema: public; Owner: -
--

CREATE SEQUENCE public.wiki_user_peptide_feedback_answers_id_seq
    AS integer
    START WITH 1
    INCREMENT BY 1
    NO MINVALUE
    NO MAXVALUE
    CACHE 1;


--
-- Name: wiki_user_peptide_feedback_answers_id_seq; Type: SEQUENCE OWNED BY; Schema: public; Owner: -
--

ALTER SEQUENCE public.wiki_user_peptide_feedback_answers_id_seq OWNED BY public.wiki_user_peptide_feedback_answers.id;


--
-- Name: wiki_user_peptide_question_answers; Type: TABLE; Schema: public; Owner: -
--

CREATE TABLE public.wiki_user_peptide_question_answers (
    id integer NOT NULL,
    user_id uuid NOT NULL,
    peptide_id integer,
    question_id integer NOT NULL,
    option_id integer NOT NULL,
    answered_at timestamp with time zone DEFAULT now() NOT NULL
);


--
-- Name: wiki_user_peptide_question_answers_id_seq; Type: SEQUENCE; Schema: public; Owner: -
--

CREATE SEQUENCE public.wiki_user_peptide_question_answers_id_seq
    AS integer
    START WITH 1
    INCREMENT BY 1
    NO MINVALUE
    NO MAXVALUE
    CACHE 1;


--
-- Name: wiki_user_peptide_question_answers_id_seq; Type: SEQUENCE OWNED BY; Schema: public; Owner: -
--

ALTER SEQUENCE public.wiki_user_peptide_question_answers_id_seq OWNED BY public.wiki_user_peptide_question_answers.id;


--
-- Name: wiki_user_profiles; Type: TABLE; Schema: public; Owner: -
--

CREATE TABLE public.wiki_user_profiles (
    id integer NOT NULL,
    user_id uuid NOT NULL,
    bio text,
    social_links jsonb,
    is_influencer boolean DEFAULT false,
    referral_code character varying(50),
    profile_visibility character varying(20) DEFAULT 'public'::character varying,
    created_at timestamp with time zone DEFAULT now(),
    updated_at timestamp with time zone DEFAULT now()
);


--
-- Name: wiki_user_profiles_id_seq; Type: SEQUENCE; Schema: public; Owner: -
--

CREATE SEQUENCE public.wiki_user_profiles_id_seq
    AS integer
    START WITH 1
    INCREMENT BY 1
    NO MINVALUE
    NO MAXVALUE
    CACHE 1;


--
-- Name: wiki_user_profiles_id_seq; Type: SEQUENCE OWNED BY; Schema: public; Owner: -
--

ALTER SEQUENCE public.wiki_user_profiles_id_seq OWNED BY public.wiki_user_profiles.id;


--
-- Name: administration_methods id; Type: DEFAULT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.administration_methods ALTER COLUMN id SET DEFAULT nextval('public.administration_methods_id_seq'::regclass);


--
-- Name: app_analytics id; Type: DEFAULT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.app_analytics ALTER COLUMN id SET DEFAULT nextval('public.app_analytics_id_seq'::regclass);


--
-- Name: application_places id; Type: DEFAULT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.application_places ALTER COLUMN id SET DEFAULT nextval('public.application_places_id_seq'::regclass);


--
-- Name: benefits id; Type: DEFAULT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.benefits ALTER COLUMN id SET DEFAULT nextval('public.benefits_id_seq'::regclass);


--
-- Name: calc_analytics id; Type: DEFAULT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.calc_analytics ALTER COLUMN id SET DEFAULT nextval('public.calc_analytics_id_seq'::regclass);


--
-- Name: calc_daily_stats id; Type: DEFAULT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.calc_daily_stats ALTER COLUMN id SET DEFAULT nextval('public.calc_daily_stats_id_seq'::regclass);


--
-- Name: calc_user_profiles id; Type: DEFAULT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.calc_user_profiles ALTER COLUMN id SET DEFAULT nextval('public.calc_user_profiles_id_seq'::regclass);


--
-- Name: calc_user_reviews id; Type: DEFAULT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.calc_user_reviews ALTER COLUMN id SET DEFAULT nextval('public.calc_user_reviews_id_seq'::regclass);


--
-- Name: categories id; Type: DEFAULT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.categories ALTER COLUMN id SET DEFAULT nextval('public.categories_id_seq'::regclass);


--
-- Name: citations id; Type: DEFAULT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.citations ALTER COLUMN id SET DEFAULT nextval('public.citations_id_seq'::regclass);


--
-- Name: dosages id; Type: DEFAULT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.dosages ALTER COLUMN id SET DEFAULT nextval('public.dosages_id_seq'::regclass);


--
-- Name: feedback_questions id; Type: DEFAULT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.feedback_questions ALTER COLUMN id SET DEFAULT nextval('public.feedback_questions_id_seq'::regclass);


--
-- Name: influencer_profiles id; Type: DEFAULT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.influencer_profiles ALTER COLUMN id SET DEFAULT nextval('public.influencer_profiles_id_seq'::regclass);


--
-- Name: pepti_price_analytics id; Type: DEFAULT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.pepti_price_analytics ALTER COLUMN id SET DEFAULT nextval('public.pepti_price_analytics_id_seq'::regclass);


--
-- Name: pepti_price_daily_stats id; Type: DEFAULT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.pepti_price_daily_stats ALTER COLUMN id SET DEFAULT nextval('public.pepti_price_daily_stats_id_seq'::regclass);


--
-- Name: pepti_price_newsletter_subscribers id; Type: DEFAULT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.pepti_price_newsletter_subscribers ALTER COLUMN id SET DEFAULT nextval('public.pepti_price_newsletter_subscribers_id_seq'::regclass);


--
-- Name: pepti_price_notifications id; Type: DEFAULT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.pepti_price_notifications ALTER COLUMN id SET DEFAULT nextval('public.pepti_price_notifications_id_seq'::regclass);


--
-- Name: pepti_price_price_history id; Type: DEFAULT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.pepti_price_price_history ALTER COLUMN id SET DEFAULT nextval('public.pepti_price_price_history_id_seq'::regclass);


--
-- Name: pepti_price_promo_codes id; Type: DEFAULT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.pepti_price_promo_codes ALTER COLUMN id SET DEFAULT nextval('public.pepti_price_promo_codes_id_seq'::regclass);


--
-- Name: pepti_price_vendor_pricing id; Type: DEFAULT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.pepti_price_vendor_pricing ALTER COLUMN id SET DEFAULT nextval('public.pepti_price_vendor_pricing_id_seq'::regclass);


--
-- Name: pepti_price_watchlist id; Type: DEFAULT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.pepti_price_watchlist ALTER COLUMN id SET DEFAULT nextval('public.pepti_price_watchlist_id_seq'::regclass);


--
-- Name: peptide_benefits id; Type: DEFAULT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.peptide_benefits ALTER COLUMN id SET DEFAULT nextval('public.peptide_benefits_id_seq'::regclass);


--
-- Name: peptide_interactions id; Type: DEFAULT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.peptide_interactions ALTER COLUMN id SET DEFAULT nextval('public.peptide_interactions_id_seq'::regclass);


--
-- Name: peptide_protocol_reconstitution_steps id; Type: DEFAULT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.peptide_protocol_reconstitution_steps ALTER COLUMN id SET DEFAULT nextval('public.peptide_protocol_reconstitution_steps_id_seq'::regclass);


--
-- Name: peptide_protocols id; Type: DEFAULT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.peptide_protocols ALTER COLUMN id SET DEFAULT nextval('public.peptide_protocols_id_seq'::regclass);


--
-- Name: peptide_question_assignments id; Type: DEFAULT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.peptide_question_assignments ALTER COLUMN id SET DEFAULT nextval('public.peptide_question_assignments_id_seq'::regclass);


--
-- Name: peptide_question_option_assignments id; Type: DEFAULT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.peptide_question_option_assignments ALTER COLUMN id SET DEFAULT nextval('public.peptide_question_option_assignments_id_seq'::regclass);


--
-- Name: peptide_question_options id; Type: DEFAULT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.peptide_question_options ALTER COLUMN id SET DEFAULT nextval('public.peptide_question_options_id_seq'::regclass);


--
-- Name: peptide_questions id; Type: DEFAULT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.peptide_questions ALTER COLUMN id SET DEFAULT nextval('public.peptide_questions_id_seq'::regclass);


--
-- Name: peptide_references id; Type: DEFAULT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.peptide_references ALTER COLUMN id SET DEFAULT nextval('public.peptide_references_id_seq'::regclass);


--
-- Name: peptide_research_indication_studies id; Type: DEFAULT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.peptide_research_indication_studies ALTER COLUMN id SET DEFAULT nextval('public.peptide_research_indication_studies_id_seq'::regclass);


--
-- Name: peptide_research_indications id; Type: DEFAULT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.peptide_research_indications ALTER COLUMN id SET DEFAULT nextval('public.peptide_research_indications_id_seq'::regclass);


--
-- Name: peptide_side_effects id; Type: DEFAULT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.peptide_side_effects ALTER COLUMN id SET DEFAULT nextval('public.peptide_side_effects_id_seq'::regclass);


--
-- Name: peptides id; Type: DEFAULT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.peptides ALTER COLUMN id SET DEFAULT nextval('public.peptides_id_seq'::regclass);


--
-- Name: protocol_application_places id; Type: DEFAULT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.protocol_application_places ALTER COLUMN id SET DEFAULT nextval('public.protocol_application_places_id_seq'::regclass);


--
-- Name: protocol_dosage_benefits id; Type: DEFAULT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.protocol_dosage_benefits ALTER COLUMN id SET DEFAULT nextval('public.protocol_dosage_benefits_id_seq'::regclass);


--
-- Name: protocol_dosage_side_effects id; Type: DEFAULT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.protocol_dosage_side_effects ALTER COLUMN id SET DEFAULT nextval('public.protocol_dosage_side_effects_id_seq'::regclass);


--
-- Name: protocol_dosages id; Type: DEFAULT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.protocol_dosages ALTER COLUMN id SET DEFAULT nextval('public.protocol_dosages_id_seq'::regclass);


--
-- Name: protocol_quality_indicators id; Type: DEFAULT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.protocol_quality_indicators ALTER COLUMN id SET DEFAULT nextval('public.protocol_quality_indicators_id_seq'::regclass);


--
-- Name: research_studies id; Type: DEFAULT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.research_studies ALTER COLUMN id SET DEFAULT nextval('public.research_studies_id_seq'::regclass);


--
-- Name: roles id; Type: DEFAULT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.roles ALTER COLUMN id SET DEFAULT nextval('public.roles_id_seq'::regclass);


--
-- Name: schedules id; Type: DEFAULT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.schedules ALTER COLUMN id SET DEFAULT nextval('public.schedules_id_seq'::regclass);


--
-- Name: sds_analytics id; Type: DEFAULT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.sds_analytics ALTER COLUMN id SET DEFAULT nextval('public.sds_analytics_id_seq'::regclass);


--
-- Name: side_effects id; Type: DEFAULT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.side_effects ALTER COLUMN id SET DEFAULT nextval('public.side_effects_id_seq'::regclass);


--
-- Name: user_roles id; Type: DEFAULT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.user_roles ALTER COLUMN id SET DEFAULT nextval('public.user_roles_id_seq'::regclass);


--
-- Name: user_suggestions id; Type: DEFAULT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.user_suggestions ALTER COLUMN id SET DEFAULT nextval('public.user_suggestions_id_seq'::regclass);


--
-- Name: vendor_peptides id; Type: DEFAULT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.vendor_peptides ALTER COLUMN id SET DEFAULT nextval('public.vendor_peptides_id_seq'::regclass);


--
-- Name: vendors id; Type: DEFAULT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.vendors ALTER COLUMN id SET DEFAULT nextval('public.vendors_id_seq'::regclass);


--
-- Name: wiki_coupons id; Type: DEFAULT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.wiki_coupons ALTER COLUMN id SET DEFAULT nextval('public.wiki_coupons_id_seq'::regclass);


--
-- Name: wiki_influencer_analytics id; Type: DEFAULT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.wiki_influencer_analytics ALTER COLUMN id SET DEFAULT nextval('public.wiki_influencer_analytics_id_seq'::regclass);


--
-- Name: wiki_peptide_analytics id; Type: DEFAULT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.wiki_peptide_analytics ALTER COLUMN id SET DEFAULT nextval('public.wiki_peptide_analytics_id_seq'::regclass);


--
-- Name: wiki_posts id; Type: DEFAULT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.wiki_posts ALTER COLUMN id SET DEFAULT nextval('public.wiki_posts_id_seq'::regclass);


--
-- Name: wiki_referral_banners id; Type: DEFAULT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.wiki_referral_banners ALTER COLUMN id SET DEFAULT nextval('public.wiki_referral_banners_id_seq'::regclass);


--
-- Name: wiki_referral_clicks id; Type: DEFAULT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.wiki_referral_clicks ALTER COLUMN id SET DEFAULT nextval('public.wiki_referral_clicks_id_seq'::regclass);


--
-- Name: wiki_trending_peptides id; Type: DEFAULT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.wiki_trending_peptides ALTER COLUMN id SET DEFAULT nextval('public.wiki_trending_peptides_id_seq'::regclass);


--
-- Name: wiki_user_peptide_feedback_answers id; Type: DEFAULT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.wiki_user_peptide_feedback_answers ALTER COLUMN id SET DEFAULT nextval('public.wiki_user_peptide_feedback_answers_id_seq'::regclass);


--
-- Name: wiki_user_peptide_question_answers id; Type: DEFAULT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.wiki_user_peptide_question_answers ALTER COLUMN id SET DEFAULT nextval('public.wiki_user_peptide_question_answers_id_seq'::regclass);


--
-- Name: wiki_user_profiles id; Type: DEFAULT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.wiki_user_profiles ALTER COLUMN id SET DEFAULT nextval('public.wiki_user_profiles_id_seq'::regclass);


--
-- Data for Name: administration_methods; Type: TABLE DATA; Schema: public; Owner: -
--

COPY public.administration_methods (id, name, description, icon, color_bg, color_text, sort_order, is_active, deleted_at, created_at, updated_at) FROM stdin;
1	Injectable	Subcutaneous or intramuscular injection	Syringe	#E3F2FD	#1976D2	1	t	\N	2025-07-15 17:14:31+00	2025-07-19 14:57:38+00
2	Capsule	Oral capsule form	Pill	#F3E5F5	#7B1FA2	2	t	\N	2025-07-15 17:14:31+00	2025-07-19 14:57:59+00
3	Nasal Spray	Intranasal administration	Spray	#E8F5E8	#388E3C	3	t	\N	2025-07-15 17:14:31+00	2025-07-19 14:58:10+00
4	Topical Cream	Applied to skin surface	Hand	#FFF3E0	#F57C00	4	t	\N	2025-07-15 17:14:31+00	2025-07-19 14:58:17+00
\.


--
-- Data for Name: app_analytics; Type: TABLE DATA; Schema: public; Owner: -
--

COPY public.app_analytics (id, app_id, event_type, entity_type, entity_id, user_id, session_id, metadata, ip_address, user_agent, "timestamp", created_at) FROM stdin;
\.


--
-- Data for Name: app_credit_costs; Type: TABLE DATA; Schema: public; Owner: -
--

COPY public.app_credit_costs (id, feature_key, credits_required, description, is_active, created_at, updated_at, app_source) FROM stdin;
10d604dc-c527-45ba-98c7-9c85d28f0635	sds_batch	8	Batch download — 8 credits per document	t	2026-04-23 01:28:32.58654+00	2026-04-23 01:39:39.248784+00	sds
7ebbe32b-55ca-4c8c-8291-7454ba619d6f	sds_remove_watermark	2	Remove watermark from SDS report	t	2026-04-23 01:28:32.58654+00	2026-04-23 01:39:39.248784+00	sds
4ef5527d-4e41-4f6e-8f12-ed23e840c4cf	sds_custom_logo	3	Use custom uploaded logo on SDS report	t	2026-04-23 01:28:32.58654+00	2026-04-23 01:39:39.248784+00	sds
ddc6b7ff-8210-4f52-9f45-1df075193a2b	sds_generate	15	Base SDS report generation (includes watermark and font-only logo)	t	2026-04-23 01:28:32.58654+00	2026-05-05 14:56:55.682775+00	sds
\.


--
-- Data for Name: app_sources; Type: TABLE DATA; Schema: public; Owner: -
--

COPY public.app_sources (code, label, is_active, created_at) FROM stdin;
admin	Admin Panel	t	2026-04-23 01:28:32.58654+00
wiki	Wiki App	t	2026-04-23 01:28:32.58654+00
influencer	 Influencer App	t	2026-04-23 01:39:38.747542+00
calculator	Calculator App	t	2026-04-23 01:28:32.58654+00
pepti_price	Pepti Price App	t	2026-04-23 01:28:32.58654+00
sds	SDS App	t	2026-04-23 01:28:32.58654+00
\.


--
-- Data for Name: application_places; Type: TABLE DATA; Schema: public; Owner: -
--

COPY public.application_places (id, name, description, anatomical_region, absorption_rate, icon, color_bg, color_text, sort_order, is_active, deleted_at, created_at, updated_at, instructions) FROM stdin;
\.


--
-- Data for Name: benefits; Type: TABLE DATA; Schema: public; Owner: -
--

COPY public.benefits (id, name, description, category, evidence_level, timeframe, color_bg, color_text, icon, sort_order, is_active, deleted_at, created_at, updated_at) FROM stdin;
\.


--
-- Data for Name: calc_analytics; Type: TABLE DATA; Schema: public; Owner: -
--

COPY public.calc_analytics (id, ip_address, device_uuid, action, peptide_id, page_url, user_agent, "timestamp") FROM stdin;
\.


--
-- Data for Name: calc_daily_stats; Type: TABLE DATA; Schema: public; Owner: -
--

COPY public.calc_daily_stats (id, device_uuid, date, calculations, vial_views, profile_updates, created_at) FROM stdin;
\.


--
-- Data for Name: calc_notification_devices; Type: TABLE DATA; Schema: public; Owner: -
--

COPY public.calc_notification_devices (id, notification_id, user_device_id, delivery_status, sent_at, delivered_at, failed_at, error_message, retry_count, created_at, updated_at) FROM stdin;
\.


--
-- Data for Name: calc_notifications; Type: TABLE DATA; Schema: public; Owner: -
--

COPY public.calc_notifications (id, user_id, title, body, scheduled_at, created_at, resend_count, last_resent_at, delivery_status) FROM stdin;
\.


--
-- Data for Name: calc_promo_banners; Type: TABLE DATA; Schema: public; Owner: -
--

COPY public.calc_promo_banners (id, is_visible, is_active, title, code, description, icon, store_url, button_text, days_left, hours_left, expires_at, theme_config, banner_type, priority, start_date, end_date, click_count, view_count, created_by, created_at, updated_at) FROM stdin;
\.


--
-- Data for Name: calc_user_devices; Type: TABLE DATA; Schema: public; Owner: -
--

COPY public.calc_user_devices (id, user_id, device_id, expo_push_token, platform, device_model, app_version, locale, timezone, is_active, last_seen, created_at, updated_at) FROM stdin;
0939e73d-4785-4627-a6b1-a92427ea4283	0528557a-5216-45f1-91ee-c293a95af1b0	741995c8-d08b-439e-8377-7875fefaf44c	\N	ios	iPhone Simulator	1.0.0	en-US	Asia/Dhaka	t	2026-04-28 21:47:17.439+00	2026-04-28 21:47:17.439+00	2026-04-28 21:47:17.439+00
f1a9c93c-b850-47b0-b963-d7aa56de9964	e70508c1-9ddf-4ffc-b84c-1f96aaa54b2f	bc3ba80e-f9ff-475e-bc6d-e066ad9b2a6c	\N	ios	iPhone Simulator	1.0.0	en-US	Asia/Dhaka	t	2026-04-28 21:50:37.451+00	2026-04-28 21:50:37.452+00	2026-04-28 21:50:37.452+00
ffba4f42-f409-4f54-b83a-c27361fdb9c8	fd0b3399-eb5f-416e-b270-11fc6d004c63	822764fc-451d-4992-a268-4c69b7e92ab9	ExponentPushToken[ekRoJ0Pb0rX99cL2bIaHmH]	ios	Simulator iOS	1.0.0	en-US	America/Los_Angeles	t	2026-04-28 22:08:33.926+00	2026-04-28 22:08:31.715+00	2026-04-28 22:08:33.926+00
2eee598e-1980-4667-995c-62824580c798	342749e0-e1a7-403c-8bc1-a276cd712fcf	d814e1e5-9d99-4fa2-adfd-a420613a18df	ExponentPushToken[pRZ3l8B24AO7TpXJvCFDt_]	ios	iPhone 17 Pro Max	1.0.0	en-CO	America/Los_Angeles	t	2026-04-28 22:15:21.918+00	2026-04-28 22:15:19.501+00	2026-04-28 22:15:21.918+00
189679c2-93a3-47f7-822b-17c0f413525e	1bcf4777-9ddf-461c-ab6b-ac17e8dcfef4	0774cac6-11cd-45a9-aed2-9da902300b01	\N	android	sdk_gphone64_arm64	1.0.0	en-US	Asia/Dhaka	t	2026-05-02 17:50:21.146+00	2026-04-28 21:55:15.387+00	2026-05-02 17:50:21.146+00
c954d0dd-ca00-4d50-b3de-3d8b2d939f41	d51a6f46-da6c-48ec-98e9-82cfb0f281ac	e964bf59-12c4-4b06-8b76-d2b6a6897268	ExponentPushToken[sZUUEZHP_7FPl8r329dDuM]	ios	Simulator iOS	1.0.0	en-BD	Asia/Dhaka	t	2026-05-02 17:50:27.548+00	2026-05-02 17:47:48.692+00	2026-05-02 17:50:27.548+00
\.


--
-- Data for Name: calc_user_profiles; Type: TABLE DATA; Schema: public; Owner: -
--

COPY public.calc_user_profiles (id, user_id, terms_accepted, terms_accepted_at, terms_version, preferences, created_at, updated_at) FROM stdin;
1	0528557a-5216-45f1-91ee-c293a95af1b0	t	2026-04-28 21:47:22.4+00	\N	\N	2026-04-28 21:47:17.438+00	2026-04-28 21:47:22.4+00
3	e70508c1-9ddf-4ffc-b84c-1f96aaa54b2f	f	\N	\N	\N	2026-04-28 21:50:37.451+00	2026-04-28 21:50:37.451+00
6	fd0b3399-eb5f-416e-b270-11fc6d004c63	t	2026-04-28 22:08:41.866+00	\N	\N	2026-04-28 22:08:31.714+00	2026-04-28 22:08:41.866+00
10	342749e0-e1a7-403c-8bc1-a276cd712fcf	t	2026-04-28 22:15:21.918+00	\N	\N	2026-04-28 22:15:19.501+00	2026-04-28 22:15:21.918+00
4	1bcf4777-9ddf-461c-ab6b-ac17e8dcfef4	t	2026-05-02 17:50:21.146+00	\N	\N	2026-04-28 21:55:15.386+00	2026-05-02 17:50:21.146+00
30	d51a6f46-da6c-48ec-98e9-82cfb0f281ac	t	2026-05-02 17:50:45.899+00	\N	\N	2026-05-02 17:47:48.692+00	2026-05-02 17:50:45.899+00
\.


--
-- Data for Name: calc_user_reviews; Type: TABLE DATA; Schema: public; Owner: -
--

COPY public.calc_user_reviews (id, user_id, rating, review_text, is_active, created_at, updated_at) FROM stdin;
\.


--
-- Data for Name: calc_vials; Type: TABLE DATA; Schema: public; Owner: -
--

COPY public.calc_vials (id, user_id, peptide_name, syringe_size, unit, dose_unit, peptide_amount, bac_water, desired_amount, calculated_output, peptide_amount_unit, is_active, deleted_at, created_at, updated_at) FROM stdin;
22083e72-1d33-49ee-bbfd-37fb73e8b427	1bcf4777-9ddf-461c-ab6b-ac17e8dcfef4	test	100	Units	mcg	1234.0000	1.0000	6.0000	0.5	mcg	t	\N	2026-05-02 17:01:29.588+00	2026-05-02 17:01:29.588+00
\.


--
-- Data for Name: categories; Type: TABLE DATA; Schema: public; Owner: -
--

COPY public.categories (id, parent_category_id, category_name, slug, color_bg, color_text, icon, deleted_at, created_at, updated_at) FROM stdin;
100	\N	Health & Wellness	health-wellness	#FFFFFF	#000000	Heart	\N	2026-04-23 01:37:27.698168+00	2026-04-23 01:37:27.698168+00
101	\N	Performance & Recovery	performance-recovery	#FFFFFF	#000000	Dumbbell	\N	2026-04-23 01:37:27.698168+00	2026-04-23 01:37:27.698168+00
102	\N	Beauty & Anti-Aging	beauty-anti-aging	#FFFFFF	#000000	Sparkles	\N	2026-04-23 01:37:27.698168+00	2026-04-23 01:37:27.698168+00
103	\N	Brain & Mood	brain-mood	#FFFFFF	#000000	Brain	\N	2026-04-23 01:37:27.698168+00	2026-04-23 01:37:27.698168+00
104	\N	Metabolic & Weight	metabolic-weight	#FFFFFF	#000000	Scale	\N	2026-04-23 01:37:27.698168+00	2026-04-23 01:37:27.698168+00
105	\N	Sexual & Reproductive	sexual-reproductive	#FFFFFF	#000000	VenusMars	\N	2026-04-23 01:37:27.698168+00	2026-04-23 01:37:27.698168+00
1	\N	Uncategorized	uncategorized	#E0E0E0	#000000	Tag	\N	2025-04-15 02:28:26+00	2025-04-15 02:28:26+00
3	101	Regeneration	regeneration	#E8F5E9	#2E7D32	Dna	\N	2025-04-15 02:28:26+00	2025-04-15 02:28:26+00
27	101	Tissue Remodeling	tissue-remodeling	#E3F2FD	#1565C0	Dna	\N	2025-08-31 21:10:33+00	2025-08-31 21:10:33+00
28	101	Anabolic	anabolic	#E3F2FD	#1565C0	Syringe	\N	2025-09-07 21:23:32+00	2025-10-05 08:41:38+00
4	105	Hormonal	hormonal	#FFEBEE	#C62828	FlaskConical	\N	2025-04-15 02:28:26+00	2025-04-15 02:28:26+00
5	100	Anti-inflammatory	anti-inflammatory	#FFF3E0	#E65100	Pill	\N	2025-04-15 02:28:26+00	2025-04-15 02:28:26+00
18	100	Immune Modulation	immune-modulation	#EFEBE9	#4E342E	Stethoscope	\N	2025-04-15 02:28:26+00	2025-04-15 02:28:26+00
24	100	Bioregulator	bioregulator	#E0F2F1	#00796B	Dna	\N	2025-08-06 20:14:24+00	2025-08-06 20:14:24+00
20	102	Longevity	longevity	#ECEFF1	#455A64	Heart	\N	2025-04-15 02:28:26+00	2025-04-15 02:28:26+00
13	103	Neuropeptide	neuropeptide	#E3F2FD	#1565C0	Brain	\N	2025-04-15 02:28:26+00	2025-04-15 02:28:26+00
21	103	Cognition	cognition	#E3F2FD	#1565C0	Notebook	\N	2025-04-15 02:28:26+00	2025-04-15 02:28:26+00
25	103	Nootropic	nootropic	#E3F2FD	#1565C0	Brain	\N	2025-08-06 20:14:47+00	2025-08-06 20:14:47+00
19	104	Metabolic	metabolic	#FFF8E1	#F9A825	Beaker	\N	2025-04-15 02:28:26+00	2025-04-15 02:28:26+00
29	104	Solvent	solvent	#E3F2FD	#1565C0	Beaker	\N	2025-10-05 08:40:48+00	2025-10-05 08:41:06+00
\.


--
-- Data for Name: citations; Type: TABLE DATA; Schema: public; Owner: -
--

COPY public.citations (id, title, doi, publication_url, authors, journal, publication_year, abstract, created_at, updated_at) FROM stdin;
\.


--
-- Data for Name: credit_accounts; Type: TABLE DATA; Schema: public; Owner: -
--

COPY public.credit_accounts (id, user_id, balance, lifetime_credits_purchased, created_at, updated_at) FROM stdin;
\.


--
-- Data for Name: credit_packages; Type: TABLE DATA; Schema: public; Owner: -
--

COPY public.credit_packages (id, name, credits, price_usd_cents, stripe_price_id, is_active, created_at, updated_at, sort_order, app_source) FROM stdin;
210a72ec-8a6d-4357-9542-2c16b8b8850e	Starter	20	2000	price_starter_placeholder	t	2026-04-23 01:39:39.248784+00	2026-04-23 01:39:39.248784+00	0	\N
3b1bcfb6-3809-4630-9612-4335bab578ce	Standard	60	5000	price_standard_placeholder	t	2026-04-23 01:39:39.248784+00	2026-04-23 01:39:39.248784+00	1	\N
5638ff4e-672c-4fa2-bccd-c1005435617d	Best value	140	10000	price_best_value_placeholder	t	2026-04-23 01:39:39.248784+00	2026-04-23 01:39:39.248784+00	2	\N
\.


--
-- Data for Name: credit_transactions; Type: TABLE DATA; Schema: public; Owner: -
--

COPY public.credit_transactions (id, user_id, type, amount, balance_after, description, reference_id, created_at, credit_package_id, metadata, app_source, credit_account_id) FROM stdin;
\.


--
-- Data for Name: dosages; Type: TABLE DATA; Schema: public; Owner: -
--

COPY public.dosages (id, name, amount, unit, description, severity_level, color_bg, color_text, icon, sort_order, is_active, deleted_at, created_at, updated_at) FROM stdin;
1	Low Dose	100.0000	mcg	Starting/maintenance dose	low	#E8F5E8	#2E7D32	Microscope	1	t	\N	2025-07-15 17:14:31+00	2025-07-24 02:52:00+00
2	Standard Dose	250.0000	mcg	Recommended therapeutic dose	medium	#FFF3E0	#EF6C00	Microscope	2	t	\N	2025-07-15 17:14:31+00	2025-07-24 02:52:07+00
3	High Dose test	500.0000	mcg	Maximum therapeutic dose	high	#FFEBEE	#C62828	Microscope	3	t	\N	2025-07-15 17:14:31+00	2025-07-24 02:52:14+00
20	Standard Dosage	5.0000	mg	\N	medium	#E3F2FD	#1565C0	Syringe	0	t	\N	2025-08-06 21:04:56+00	2025-08-06 21:04:56+00
21	Frequent dosing	100.0000	mcg	Frequent Dosing for Stable blood levels.	high	#E3F2FD	#1565C0	Activity	0	t	\N	2025-08-06 23:42:46+00	2025-08-06 23:42:46+00
22	Low Dose	1.0000	mg	Low dose once a day	low	#E3F2FD	#1565C0	Activity	0	t	\N	2025-08-07 18:43:48+00	2025-08-07 18:43:48+00
23	Optimal Dose	2.0000	mg	Optimal dose. Once a day.	medium	#E3F2FD	#1565C0	Activity	0	t	\N	2025-08-07 18:44:13+00	2025-08-07 18:44:13+00
24	Standard Dose	125.0000	mcg	SubQ Injections	medium	#E3F2FD	#1565C0	Activity	0	t	\N	2025-08-07 20:14:59+00	2025-08-07 20:14:59+00
25	Standard dose	125.0000	mcg	SubQ Injection	medium	#E3F2FD	#1565C0	Activity	0	t	\N	2025-08-07 20:16:57+00	2025-08-07 20:16:57+00
26	Split dose	60.0000	mcg	Ideal for more stable blood levels.	medium	#E3F2FD	#1565C0	Activity	0	t	\N	2025-08-07 20:25:57+00	2025-08-07 20:25:57+00
27	Topical Cream	0.5000	mg/ml	\N	low	#E3F2FD	#1565C0	Activity	0	t	\N	2025-08-07 20:36:00+00	2025-08-07 20:36:00+00
28	Topical Cream	1.0000	mg/ml	\N	medium	#E3F2FD	#1565C0	Activity	0	t	\N	2025-08-07 20:36:27+00	2025-08-07 20:36:27+00
29	Topical Cream	1.5000	mg/ml	\N	high	#E3F2FD	#1565C0	Activity	0	t	\N	2025-08-07 20:36:51+00	2025-08-07 20:36:51+00
30	Medium Dose	5.0000	mg	\N	medium	#E3F2FD	#1565C0	Activity	0	t	\N	2025-08-07 21:15:05+00	2025-08-07 21:15:05+00
31	High Dose	10.0000	mg	\N	medium	#E3F2FD	#1565C0	Activity	0	t	\N	2025-08-07 21:15:26+00	2025-08-07 21:15:26+00
32	Topical Cream	2.0000	%	\N	low	#E3F2FD	#1565C0	Activity	0	t	\N	2025-08-07 21:23:32+00	2025-08-07 21:23:32+00
33	Topical Cream	5.0000	%	\N	medium	#E3F2FD	#1565C0	Activity	0	t	\N	2025-08-07 21:23:46+00	2025-08-07 21:23:46+00
34	Topical Cream	10.0000	%	\N	medium	#E3F2FD	#1565C0	Activity	0	t	\N	2025-08-07 21:24:08+00	2025-08-07 21:24:08+00
35	Low Dose	2.0000	mg	\N	low	#E3F2FD	#1565C0	Activity	0	t	\N	2025-08-08 00:24:12+00	2025-08-08 00:24:12+00
37	High Dose	500.0000	mcg	\N	high	#E3F2FD	#1565C0	Activity	0	t	\N	2025-08-08 01:12:01+00	2025-08-08 01:12:01+00
38	Low Dose	500.0000	mcg	\N	low	#E3F2FD	#1565C0	Activity	0	t	\N	2025-08-08 01:19:16+00	2025-08-08 01:19:16+00
39	Standard dose	1.0000	mg	\N	medium	#E3F2FD	#1565C0	Activity	0	t	\N	2025-08-08 01:19:35+00	2025-08-08 01:19:35+00
40	High Dose	2.0000	mg	\N	high	#E3F2FD	#1565C0	Activity	0	t	\N	2025-08-08 01:20:03+00	2025-08-08 01:20:03+00
41	Very High Dose	4.0000	mg	\N	critical	#E3F2FD	#1565C0	Activity	0	t	\N	2025-08-08 01:20:23+00	2025-08-08 01:20:23+00
42	Medium dose	4.0000	mg	\N	low	#E3F2FD	#1565C0	Activity	0	t	\N	2025-08-08 05:24:51+00	2025-08-08 05:24:51+00
45	Low Dose	2.0000	mcg	\N	low	#E3F2FD	#1565C0	Activity	0	t	\N	2025-08-13 12:41:01+00	2025-08-13 12:41:01+00
46	Medium Dose	50.0000	mcg	\N	medium	#E3F2FD	#1565C0	Activity	0	t	\N	2025-08-13 12:41:12+00	2025-08-13 12:41:12+00
47	High Dose	100.0000	mcg	\N	medium	#E3F2FD	#1565C0	Activity	0	t	\N	2025-08-13 12:41:24+00	2025-08-13 12:41:24+00
48	Low Dosage	20.0000	mcg	\N	low	#E3F2FD	#1565C0	Activity	0	t	\N	2025-08-13 12:42:54+00	2025-08-13 12:42:54+00
49	Standard Dose	50.0000	mg	\N	medium	#E3F2FD	#1565C0	Activity	0	t	\N	2025-08-14 22:29:54+00	2025-08-14 22:29:54+00
50	High Dose	100.0000	mg	\N	high	#E3F2FD	#1565C0	Activity	0	t	\N	2025-08-14 22:30:47+00	2025-08-14 22:30:47+00
51	Low dose	10.0000	mg	\N	medium	#E3F2FD	#1565C0	Activity	0	t	\N	2025-08-14 22:41:48+00	2025-08-14 22:41:48+00
52	Medium dose	25.0000	mg	\N	medium	#E3F2FD	#1565C0	Activity	0	t	\N	2025-08-14 22:42:02+00	2025-08-14 22:42:02+00
53	High Dose	50.0000	mg	\N	high	#E3F2FD	#1565C0	Activity	0	t	\N	2025-08-14 22:42:15+00	2025-08-14 22:42:15+00
54	Medium dose	500.0000	mcg	\N	medium	#E3F2FD	#1565C0	Activity	0	t	\N	2025-08-19 18:49:49+00	2025-08-19 18:49:49+00
55	High dose	1.0000	mg	\N	high	#E3F2FD	#1565C0	Activity	0	t	\N	2025-08-19 18:50:17+00	2025-08-19 18:50:17+00
56	Topical cream	0.1000	%	\N	medium	#E3F2FD	#1565C0	Activity	0	t	\N	2025-08-19 18:52:17+00	2025-08-19 18:52:17+00
57	Universal Dosage	300.0000	mcg	\N	medium	#E3F2FD	#1565C0	Activity	0	t	\N	2025-08-19 23:17:22+00	2025-08-19 23:17:22+00
58	High Dosage	400.0000	mcg	\N	medium	#E3F2FD	#1565C0	Activity	0	t	\N	2025-08-19 23:19:14+00	2025-08-19 23:19:14+00
59	Low dose	0.2500	mg	\N	low	#E3F2FD	#1565C0	Activity	0	t	\N	2025-08-20 00:40:47+00	2025-08-20 00:40:47+00
60	Medium dose	0.5000	mg	\N	medium	#E3F2FD	#1565C0	Activity	0	t	\N	2025-08-20 00:42:28+00	2025-08-20 00:42:28+00
61	Very High Dose	3.0000	mg	\N	high	#E3F2FD	#1565C0	Activity	0	t	\N	2025-08-20 01:01:07+00	2025-08-20 01:01:07+00
62	Low dose	100.0000	mcg	\N	low	#E3F2FD	#1565C0	Activity	0	t	\N	2025-08-21 01:33:43+00	2025-08-21 01:34:24+00
63	Medium dose	250.0000	mcg	\N	medium	#E3F2FD	#1565C0	Activity	0	t	\N	2025-08-21 01:35:28+00	2025-08-21 01:35:28+00
64	Medium dose	2.0000	mg	\N	medium	#E3F2FD	#1565C0	Activity	0	t	\N	2025-08-21 01:38:22+00	2025-08-21 01:38:22+00
65	High dose	5.0000	mg	\N	medium	#E3F2FD	#1565C0	Activity	0	t	\N	2025-08-21 01:38:31+00	2025-08-21 01:38:31+00
66	Low dose	35.0000	mg	\N	low	#E3F2FD	#1565C0	Activity	0	t	\N	2025-08-21 16:03:57+00	2025-08-21 16:03:57+00
67	Medium dose	70.0000	mg	\N	medium	#E3F2FD	#1565C0	Activity	0	t	\N	2025-08-21 16:04:10+00	2025-08-21 16:04:10+00
68	High dose	125.0000	mg	\N	medium	#E3F2FD	#1565C0	Activity	0	t	\N	2025-08-21 16:04:25+00	2025-08-21 16:04:25+00
69	Very high dose	200.0000	mg	\N	medium	#E3F2FD	#1565C0	Activity	0	t	\N	2025-08-21 16:04:36+00	2025-08-21 16:04:36+00
70	Low dose	150.0000	mcg	\N	low	#E3F2FD	#1565C0	Activity	0	t	\N	2025-08-22 01:03:51+00	2025-08-22 01:03:51+00
71	Medium dose	300.0000	mcg	\N	medium	#E3F2FD	#1565C0	Activity	0	t	\N	2025-08-22 01:04:07+00	2025-08-22 01:04:07+00
72	High dose	500.0000	mcg	\N	high	#E3F2FD	#1565C0	Activity	0	t	\N	2025-08-22 01:04:23+00	2025-08-22 01:04:23+00
75	High dose	6.0000	mg	\N	high	#E3F2FD	#1565C0	Activity	0	t	\N	2025-08-22 01:33:22+00	2025-08-22 01:33:22+00
76	Low dose	5.0000	mg	\N	low	#E3F2FD	#1565C0	Activity	0	t	\N	2025-08-23 02:20:58+00	2025-08-23 02:20:58+00
77	Medium dose	10.0000	mg	\N	medium	#E3F2FD	#1565C0	Activity	0	t	\N	2025-08-23 02:21:08+00	2025-08-23 02:21:08+00
78	High dose	15.0000	mg	\N	high	#E3F2FD	#1565C0	Activity	0	t	\N	2025-08-23 02:21:23+00	2025-08-23 02:21:23+00
79	Low dose	4.5000	mg	\N	medium	#E3F2FD	#1565C0	Activity	0	t	\N	2025-08-23 02:57:53+00	2025-08-23 02:57:53+00
80	Medium dose	6.0000	mg	\N	medium	#E3F2FD	#1565C0	Activity	0	t	\N	2025-08-23 02:58:05+00	2025-08-23 02:58:05+00
81	High dose	10.0000	mg	\N	high	#E3F2FD	#1565C0	Activity	0	t	\N	2025-08-23 02:58:15+00	2025-08-23 02:58:15+00
82	Low dose	10.0000	mcg	\N	low	#E3F2FD	#1565C0	Activity	0	t	\N	2025-08-26 02:05:05+00	2025-08-26 02:05:05+00
83	Medium Dose	25.0000	mcg	\N	medium	#E3F2FD	#1565C0	Activity	0	t	\N	2025-08-26 02:05:21+00	2025-08-26 02:05:21+00
84	High Dose	50.0000	mcg	\N	medium	#E3F2FD	#1565C0	Activity	0	t	\N	2025-08-26 02:05:31+00	2025-08-26 02:05:31+00
85	Low dose	600.0000	mcg	\N	medium	#E3F2FD	#1565C0	Activity	0	t	\N	2025-08-26 02:22:54+00	2025-08-26 02:22:54+00
86	Medium Dose	2400.0000	mcg	\N	high	#E3F2FD	#1565C0	Activity	0	t	\N	2025-08-26 02:23:13+00	2025-08-26 02:23:13+00
87	High Dose	6000.0000	mcg	\N	high	#E3F2FD	#1565C0	Activity	0	t	\N	2025-08-26 02:23:30+00	2025-08-26 02:23:30+00
88	Maximum Tolerable Dose	10000.0000	mcg	\N	critical	#E3F2FD	#1565C0	Activity	0	t	\N	2025-08-26 02:24:05+00	2025-08-26 02:24:05+00
89	High dose	80.0000	mcg	\N	high	#E3F2FD	#1565C0	Activity	0	t	\N	2025-08-27 03:08:00+00	2025-08-27 03:08:00+00
90	Very High Dose	200.0000	mcg	\N	critical	#E3F2FD	#1565C0	Activity	0	t	\N	2025-08-27 03:09:31+00	2025-08-27 03:09:31+00
91	Medium Dose	1.5000	mg	\N	medium	#E3F2FD	#1565C0	Activity	0	t	\N	2025-08-27 03:28:39+00	2025-08-27 03:28:39+00
92	High Dose	3.0000	mg	\N	high	#E3F2FD	#1565C0	Activity	0	t	\N	2025-08-27 03:28:56+00	2025-08-27 03:28:56+00
93	Very High Dose	4.0000	mg	\N	high	#E3F2FD	#1565C0	Activity	0	t	\N	2025-08-27 03:29:28+00	2025-08-27 03:29:28+00
94	Extreme Dose	6.0000	mg	\N	critical	#E3F2FD	#1565C0	Activity	0	t	\N	2025-08-27 03:29:42+00	2025-08-27 03:29:42+00
95	Standard Dose	225.0000	iu	\N	medium	#E3F2FD	#1565C0	Activity	0	t	\N	2025-08-27 20:46:20+00	2025-08-27 20:46:20+00
96	Standard Dose	150.0000	iu	\N	medium	#E3F2FD	#1565C0	Activity	0	t	\N	2025-08-27 20:46:29+00	2025-08-27 20:46:29+00
97	High Dose	450.0000	iu	\N	medium	#E3F2FD	#1565C0	Activity	0	t	\N	2025-08-27 20:46:43+00	2025-08-27 20:46:43+00
98	High Dose	225.0000	iu	\N	medium	#E3F2FD	#1565C0	Activity	0	t	\N	2025-08-27 20:46:51+00	2025-08-27 20:46:51+00
99	Low Dose	50.0000	mcg	\N	medium	#E3F2FD	#1565C0	Activity	0	t	\N	2025-08-27 21:18:57+00	2025-08-27 21:18:57+00
100	Medium Dose	100.0000	mcg	\N	high	#E3F2FD	#1565C0	Activity	0	t	\N	2025-08-27 21:19:11+00	2025-08-27 21:19:11+00
101	High Dose	150.0000	mcg	\N	high	#E3F2FD	#1565C0	Activity	0	t	\N	2025-08-27 21:19:26+00	2025-08-27 21:19:26+00
102	Low Dose	10.0000	mg	\N	low	#E3F2FD	#1565C0	Activity	0	t	\N	2025-08-27 21:45:44+00	2025-08-27 21:45:44+00
103	Medium dose	15.0000	mg	\N	medium	#E3F2FD	#1565C0	Activity	0	t	\N	2025-08-27 21:45:56+00	2025-08-27 21:45:56+00
104	High Dose	25.0000	mg	\N	high	#E3F2FD	#1565C0	Activity	0	t	\N	2025-08-27 21:46:08+00	2025-08-27 21:46:08+00
105	High dose	20.0000	mg	\N	medium	#E3F2FD	#1565C0	Activity	0	t	\N	2025-08-30 07:39:45+00	2025-08-30 07:39:45+00
106	Low concentration	0.0500	%	\N	medium	#E3F2FD	#1565C0	Activity	0	t	\N	2025-08-30 07:48:31+00	2025-08-30 07:48:31+00
107	Medium concentration	0.1000	%	\N	medium	#E3F2FD	#1565C0	Activity	0	t	\N	2025-08-30 07:49:08+00	2025-08-30 07:50:23+00
108	High concentration	0.5000	%	\N	high	#E3F2FD	#1565C0	Activity	0	t	\N	2025-08-30 07:49:29+00	2025-08-30 07:49:29+00
109	Very High Concentration	1.0000	%	\N	critical	#E3F2FD	#1565C0	Activity	0	t	\N	2025-08-30 07:50:48+00	2025-08-30 07:50:48+00
110	High Dose	6.0000	mg	\N	low	#E3F2FD	#1565C0	Activity	0	t	\N	2025-08-30 08:18:09+00	2025-08-30 08:18:09+00
111	Very high dose	40.0000	mg	\N	high	#E3F2FD	#1565C0	Activity	0	t	\N	2025-08-30 09:57:42+00	2025-08-30 09:57:42+00
112	High Dose	800.0000	mg	\N	high	#E3F2FD	#1565C0	Activity	0	t	\N	2025-08-31 21:15:11+00	2025-08-31 21:15:11+00
113	Medium dose	20.0000	mg	\N	medium	#E3F2FD	#1565C0	Activity	0	t	\N	2025-09-02 00:04:08+00	2025-09-02 00:04:08+00
114	Standard Dose	20.0000	mg	\N	medium	#E3F2FD	#1565C0	Activity	0	t	\N	2025-09-02 02:22:19+00	2025-09-02 02:22:19+00
115	Medium dose	2.5000	mg	\N	medium	#E3F2FD	#1565C0	Activity	0	t	\N	2025-09-02 03:39:43+00	2025-09-02 03:39:43+00
116	High Dose	30.0000	mg	\N	medium	#E3F2FD	#1565C0	Activity	0	t	\N	2025-09-02 18:21:25+00	2025-09-02 18:21:25+00
117	Low dose	25.0000	mg	\N	medium	#E3F2FD	#1565C0	Activity	0	t	\N	2025-09-03 03:03:05+00	2025-09-03 03:03:05+00
119	Maximum Tested Dose	500.0000	mg	\N	critical	#E3F2FD	#1565C0	Activity	0	t	\N	2025-09-03 03:04:02+00	2025-09-03 03:04:02+00
120	Low Dose	250.0000	mcg	\N	low	#E3F2FD	#1565C0	Activity	0	t	\N	2025-09-07 21:13:42+00	2025-09-07 21:13:42+00
121	Medium Dose	150.0000	mcg	\N	medium	#E3F2FD	#1565C0	Activity	0	t	\N	2025-09-07 21:35:00+00	2025-09-07 21:35:00+00
122	High Dose	200.0000	mcg	\N	high	#E3F2FD	#1565C0	Activity	0	t	\N	2025-09-07 21:35:50+00	2025-09-07 21:35:50+00
123	Medium Dose	4.5000	mg	\N	medium	#E3F2FD	#1565C0	Activity	0	t	\N	2025-09-07 23:03:35+00	2025-09-07 23:03:35+00
124	High Dose	8.0000	mg	\N	high	#E3F2FD	#1565C0	Activity	0	t	\N	2025-09-07 23:03:50+00	2025-09-07 23:03:50+00
125	Low dose	50.0000	mg	\N	low	#E3F2FD	#1565C0	Activity	0	t	\N	2025-09-07 23:23:02+00	2025-09-07 23:23:02+00
126	Medium Dose	100.0000	mg	\N	medium	#E3F2FD	#1565C0	Activity	0	t	\N	2025-09-07 23:23:20+00	2025-09-07 23:23:20+00
127	High Dose	200.0000	mg	\N	high	#E3F2FD	#1565C0	Activity	0	t	\N	2025-09-07 23:23:29+00	2025-09-07 23:23:29+00
128	Low Dose	100.0000	mg	\N	low	#E3F2FD	#1565C0	Activity	0	t	\N	2025-09-07 23:26:51+00	2025-09-07 23:26:51+00
129	Medium Dose	200.0000	mg	\N	medium	#E3F2FD	#1565C0	Activity	0	t	\N	2025-09-07 23:27:03+00	2025-09-07 23:27:03+00
130	High Dose	300.0000	mg	\N	medium	#E3F2FD	#1565C0	Activity	0	t	\N	2025-09-07 23:27:11+00	2025-09-07 23:27:11+00
131	Low Concentration	100.0000	mcg/ml	\N	low	#E3F2FD	#1565C0	Activity	0	t	\N	2025-09-08 01:00:10+00	2025-09-08 01:00:10+00
132	Medium Concentration	500.0000	mcg/ml	\N	medium	#E3F2FD	#1565C0	Activity	0	t	\N	2025-09-08 01:00:31+00	2025-09-08 01:00:31+00
133	High Concentration	1.0000	mg/ml	\N	medium	#E3F2FD	#1565C0	Activity	0	t	\N	2025-09-08 01:01:22+00	2025-09-08 01:01:22+00
134	Low dose	20.0000	mg	\N	low	#E3F2FD	#1565C0	Activity	0	t	\N	2025-09-10 05:23:46+00	2025-09-10 05:23:46+00
135	Medium dose	20.0000	mg	\N	low	#E3F2FD	#1565C0	Activity	0	t	\N	2025-09-10 05:24:15+00	2025-09-10 05:24:15+00
136	Low Dose	50.0000	mcg	\N	low	#E3F2FD	#1565C0	Activity	0	t	\N	2025-09-11 17:02:42+00	2025-09-11 17:02:42+00
138	Medium Dose	100.0000	mcg	\N	medium	#E3F2FD	#1565C0	Activity	0	t	\N	2025-09-11 17:03:52+00	2025-09-11 17:03:52+00
139	Medium Dose	200.0000	mcg	\N	medium	#E3F2FD	#1565C0	Activity	0	t	\N	2025-10-05 10:40:24+00	2025-10-05 10:40:24+00
140	High Dose	300.0000	mcg	\N	high	#E3F2FD	#1565C0	Activity	0	t	\N	2025-10-05 10:40:34+00	2025-10-05 10:40:34+00
141	Standard Concentration	0.5000	%	\N	medium	#E3F2FD	#1565C0	Activity	0	t	\N	2025-10-07 11:11:50+00	2025-10-07 11:11:50+00
142	Standard Concentration	0.0005	%	\N	low	#E3F2FD	#1565C0	Activity	0	t	\N	2025-10-07 12:10:22+00	2025-10-07 12:10:22+00
143	Experimental Concentration	0.0010	%	\N	medium	#E3F2FD	#1565C0	Activity	0	t	\N	2025-10-07 12:11:59+00	2025-10-07 12:11:59+00
144	Standard Dose	300.0000	mcg	\N	low	#E3F2FD	#1565C0	Activity	0	t	\N	2025-11-01 03:00:38+00	2025-11-01 03:00:38+00
145	Moderate dose	400.0000	mcg	\N	medium	#E3F2FD	#1565C0	Activity	0	t	\N	2025-11-01 03:00:50+00	2025-11-01 03:00:50+00
146	High Dose	500.0000	mcg	\N	medium	#E3F2FD	#1565C0	Activity	0	t	\N	2025-11-01 03:01:06+00	2025-11-01 03:01:06+00
147	Maximum Dose	30.0000	mg	\N	high	#E3F2FD	#1565C0	Activity	0	t	\N	2025-11-01 03:15:08+00	2025-11-01 03:15:08+00
148	Low dose	250.0000	mg	\N	low	#E3F2FD	#1565C0	Activity	0	t	\N	2025-11-01 04:11:26+00	2025-11-01 04:11:26+00
149	Maintenance Dose	500.0000	mg	\N	medium	#E3F2FD	#1565C0	Activity	0	t	\N	2025-11-01 04:11:45+00	2025-11-01 04:11:45+00
150	Loading Dose	1000.0000	mg	\N	high	#E3F2FD	#1565C0	Activity	0	t	\N	2025-11-01 04:12:23+00	2025-11-01 04:12:23+00
151	High Loading Dose	1400.0000	mg	\N	high	#E3F2FD	#1565C0	Activity	0	t	\N	2025-11-01 04:12:42+00	2025-11-01 04:12:42+00
152	Medium Dose	500.0000	mg	\N	medium	#E3F2FD	#1565C0	Activity	0	t	\N	2025-11-01 04:27:54+00	2025-11-01 04:27:54+00
153	High Dose	1000.0000	mg	\N	medium	#E3F2FD	#1565C0	Activity	0	t	\N	2025-11-01 04:28:04+00	2025-11-01 04:28:04+00
154	Low dose	25.0000	mg	\N	low	#E3F2FD	#1565C0	Activity	0	t	\N	2025-11-01 20:26:10+00	2025-11-01 20:26:10+00
155	Medium Dose	50.0000	mg	\N	medium	#E3F2FD	#1565C0	Activity	0	t	\N	2025-11-01 20:26:24+00	2025-11-01 20:26:24+00
156	High Dose	100.0000	mg	\N	medium	#E3F2FD	#1565C0	Activity	0	t	\N	2025-11-01 20:26:44+00	2025-11-01 20:26:44+00
157	High dose	4.0000	mg	\N	medium	#E3F2FD	#1565C0	Activity	0	t	\N	2025-11-02 01:51:37+00	2025-11-02 01:51:37+00
158	Maximum Dose	40.0000	mg	\N	high	#E3F2FD	#1565C0	Activity	0	t	\N	2025-11-02 04:20:14+00	2025-11-02 04:20:14+00
159	Maximum Dose	300.0000	mg	\N	critical	#E3F2FD	#1565C0	Activity	0	t	\N	2025-11-03 18:59:49+00	2025-11-03 18:59:49+00
160	Enhanced Dose	0.5000	mg	\N	medium	#E3F2FD	#1565C0	Activity	0	t	\N	2025-11-03 23:57:58+00	2025-11-03 23:57:58+00
161	Maintenance dose	0.5000	mg	\N	medium	#E3F2FD	#1565C0	Activity	0	t	\N	2025-11-03 23:59:14+00	2025-11-03 23:59:14+00
162	Intramuscular Injection	5.0000	ml	\N	medium	#E3F2FD	#1565C0	Activity	0	t	\N	2025-11-04 00:17:30+00	2025-11-04 00:17:30+00
163	IV drip	10.0000	ml	\N	medium	#E3F2FD	#1565C0	Activity	0	t	\N	2025-11-04 00:17:51+00	2025-11-04 00:17:51+00
164	Clinical Dose Low End	20.0000	ml	\N	critical	#E3F2FD	#1565C0	Activity	0	t	\N	2025-11-04 00:18:34+00	2025-11-04 00:18:34+00
165	Clinical Dose High End	50.0000	ml	\N	critical	#E3F2FD	#1565C0	Activity	0	t	\N	2025-11-04 00:18:47+00	2025-11-04 00:18:47+00
166	Low Dose	0.5000	g	\N	medium	#E3F2FD	#1565C0	Activity	0	t	\N	2025-11-04 17:33:11+00	2025-11-04 17:33:11+00
167	Moderate dose	1.0000	g	\N	medium	#E3F2FD	#1565C0	Activity	0	t	\N	2025-11-04 17:33:23+00	2025-11-04 17:33:23+00
168	High Dose	2.0000	g	\N	high	#E3F2FD	#1565C0	Activity	0	t	\N	2025-11-04 17:33:37+00	2025-11-04 17:33:37+00
169	Maximum Recommended Dose	3.5000	g	\N	critical	#E3F2FD	#1565C0	Activity	0	t	\N	2025-11-04 17:33:49+00	2025-11-04 17:33:49+00
170	Low dose	800.0000	mg	\N	low	#E3F2FD	#1565C0	Activity	0	t	\N	2025-11-04 23:09:03+00	2025-11-04 23:09:03+00
171	Moderate Dose	1800.0000	mg	\N	low	#E3F2FD	#1565C0	Activity	0	t	\N	2025-11-04 23:09:23+00	2025-11-04 23:09:23+00
172	High Dose	2400.0000	mg	\N	low	#E3F2FD	#1565C0	Activity	0	t	\N	2025-11-04 23:09:47+00	2025-11-04 23:09:47+00
173	Medium Dose	40.0000	mg	\N	low	#E3F2FD	#1565C0	Activity	0	t	\N	2025-11-05 02:25:07+00	2025-11-05 02:25:07+00
174	High Dose	80.0000	mg	\N	low	#E3F2FD	#1565C0	Activity	0	t	\N	2025-11-05 02:27:39+00	2025-11-05 02:27:39+00
175	Low dose	500.0000	mg	\N	low	#E3F2FD	#1565C0	Activity	0	t	\N	2025-11-05 19:03:06+00	2025-11-05 19:03:06+00
176	Standard dose	1.0000	g	\N	low	#E3F2FD	#1565C0	Activity	0	t	\N	2025-11-05 19:03:24+00	2025-11-05 19:03:24+00
177	High dose	1.5000	g	\N	low	#E3F2FD	#1565C0	Activity	0	t	\N	2025-11-05 19:03:37+00	2025-11-05 19:03:37+00
178	Maximum recommended dose	2.0000	g	\N	low	#E3F2FD	#1565C0	Activity	0	t	\N	2025-11-05 19:03:57+00	2025-11-05 19:03:57+00
179	Maximum Dose	100.0000	mg	\N	medium	#E3F2FD	#1565C0	Activity	0	t	\N	2025-11-05 21:57:17+00	2025-11-05 21:57:17+00
180	Low dose	2.4000	g	\N	low	#E3F2FD	#1565C0	Activity	0	t	\N	2025-11-06 21:11:10+00	2025-11-06 21:11:10+00
181	Low-High End Dose	4.0000	g	\N	medium	#E3F2FD	#1565C0	Activity	0	t	\N	2025-11-06 21:14:32+00	2025-11-06 21:14:32+00
182	Medium dose	4.2000	g	\N	medium	#E3F2FD	#1565C0	Activity	0	t	\N	2025-11-06 21:15:03+00	2025-11-06 21:15:03+00
183	Medium-High End Dose	5.4000	g	\N	medium	#E3F2FD	#1565C0	Activity	0	t	\N	2025-11-06 21:15:30+00	2025-11-06 21:15:30+00
184	High Dose	6.0000	g	\N	medium	#E3F2FD	#1565C0	Activity	0	t	\N	2025-11-06 21:15:58+00	2025-11-06 21:15:58+00
185	Moderate Dose	5.6000	g	\N	medium	#E3F2FD	#1565C0	Activity	0	t	\N	2025-11-06 21:30:54+00	2025-11-06 21:30:54+00
186	Moderate-High End Dose	7.2000	g	\N	medium	#E3F2FD	#1565C0	Activity	0	t	\N	2025-11-06 21:31:28+00	2025-11-06 21:31:28+00
187	Maximum Dose	8.0000	g	\N	medium	#E3F2FD	#1565C0	Activity	0	t	\N	2025-11-06 21:31:37+00	2025-11-06 21:31:37+00
188	Low dose	1200.0000	mg	\N	medium	#E3F2FD	#1565C0	Activity	0	t	\N	2025-11-06 22:52:09+00	2025-11-06 22:52:09+00
189	Moderate Dose	2400.0000	mg	\N	medium	#E3F2FD	#1565C0	Activity	0	t	\N	2025-11-06 22:52:25+00	2025-11-06 22:52:25+00
190	High Dose	3600.0000	mg	\N	medium	#E3F2FD	#1565C0	Activity	0	t	\N	2025-11-06 22:52:42+00	2025-11-06 22:52:42+00
191	Maximum Dose	4800.0000	mg	\N	medium	#E3F2FD	#1565C0	Activity	0	t	\N	2025-11-06 22:53:00+00	2025-11-06 22:53:00+00
192	High Dose	400.0000	mg	\N	medium	#E3F2FD	#1565C0	Activity	0	t	\N	2025-11-06 23:01:11+00	2025-11-06 23:01:11+00
193	High Dose	500.0000	mg	\N	high	#E3F2FD	#1565C0	Activity	0	t	\N	2025-11-07 03:33:34+00	2025-11-07 03:33:34+00
194	Low Dose	60.0000	mg	\N	low	#E3F2FD	#1565C0	Activity	0	t	\N	2025-11-15 01:54:01+00	2025-11-15 01:54:01+00
195	Medium Dose	90.0000	mg	\N	medium	#E3F2FD	#1565C0	Activity	0	t	\N	2025-11-15 01:54:12+00	2025-11-15 01:54:12+00
196	High Dose	120.0000	mg	\N	medium	#E3F2FD	#1565C0	Activity	0	t	\N	2025-11-15 01:54:24+00	2025-11-15 01:54:24+00
197	Standard Concentration	0.1500	%	\N	medium	#E3F2FD	#1565C0	Activity	0	t	\N	2025-11-15 02:24:01+00	2025-11-15 02:24:01+00
198	Standard Dose	30.0000	mg	\N	medium	#E3F2FD	#1565C0	Activity	0	t	\N	2025-11-16 02:22:20+00	2025-11-16 02:22:20+00
199	High Dose	60.0000	mg	\N	high	#E3F2FD	#1565C0	Activity	0	t	\N	2025-11-16 02:22:34+00	2025-11-16 02:22:34+00
200	Moderate Dose Frequent Injections	150.0000	mcg	\N	medium	#E3F2FD	#1565C0	Activity	0	t	\N	2025-11-18 03:10:50+00	2025-11-18 03:10:50+00
201	High Dose Frequent Injections	259.0000	mcg	\N	medium	#E3F2FD	#1565C0	Activity	0	t	\N	2025-11-18 03:11:16+00	2025-11-18 03:11:16+00
203	High dose	1000.0000	mcg	\N	medium	#E3F2FD	#1565C0	Activity	0	t	\N	2025-11-18 03:15:59+00	2025-11-18 03:15:59+00
204	Standard Dose	150.0000	mcg	\N	medium	#E3F2FD	#1565C0	Activity	0	t	\N	2025-11-18 03:31:24+00	2025-11-18 03:31:24+00
205	Moderate Concentration	0.3000	%	\N	medium	#E3F2FD	#1565C0	Activity	0	t	\N	2025-11-18 10:59:29+00	2025-11-18 10:59:29+00
206	High Concentration	0.5000	%	\N	medium	#E3F2FD	#1565C0	Activity	0	t	\N	2025-11-18 10:59:41+00	2025-11-18 10:59:41+00
207	Moderate dose	2.0000	g	\N	medium	#E3F2FD	#1565C0	Activity	0	t	\N	2025-11-18 11:06:53+00	2025-11-18 11:06:53+00
208	High dose	3.0000	g	\N	medium	#E3F2FD	#1565C0	Activity	0	t	\N	2025-11-18 11:07:01+00	2025-11-18 11:07:01+00
209	Low Dosage	12.0000	IU	\N	medium	#E3F2FD	#1565C0	Activity	0	t	\N	2025-11-22 06:09:21+00	2025-11-22 06:09:46+00
210	Moderate Dose	24.0000	IU	\N	medium	#E3F2FD	#1565C0	Activity	0	t	\N	2025-11-22 06:09:33+00	2025-11-22 06:09:33+00
211	High Dosage	36.0000	IU	\N	medium	#E3F2FD	#1565C0	Activity	0	t	\N	2025-11-22 06:10:02+00	2025-11-22 06:10:02+00
212	High Dosage	48.0000	IU	\N	medium	#E3F2FD	#1565C0	Activity	0	t	\N	2025-11-22 06:10:17+00	2025-11-22 06:10:17+00
213	High Dose	24.0000	IU	\N	medium	#E3F2FD	#1565C0	Activity	0	t	\N	2025-11-22 06:16:07+00	2025-11-22 06:16:07+00
214	Low Dosage	2.0000	mg	\N	low	#E3F2FD	#1565C0	Activity	0	t	\N	2025-11-26 18:10:45+00	2025-11-26 18:11:09+00
215	Low Dosage	3.0000	mg	\N	medium	#E3F2FD	#1565C0	Activity	0	t	\N	2025-11-26 18:11:19+00	2025-11-26 18:11:19+00
216	Moderate Dosage	3.0000	mg	\N	medium	#E3F2FD	#1565C0	Activity	0	t	\N	2025-11-26 18:11:32+00	2025-11-26 18:11:32+00
217	High Dosage	5.0000	mg	\N	medium	#E3F2FD	#1565C0	Activity	0	t	\N	2025-11-26 18:11:46+00	2025-11-26 18:11:46+00
218	Moderate Dosage	5.0000	mg	\N	medium	#E3F2FD	#1565C0	Activity	0	t	\N	2025-11-26 18:14:43+00	2025-11-26 18:14:43+00
219	High Dosage	75.0000	mg	\N	high	#E3F2FD	#1565C0	Activity	0	t	\N	2025-12-04 16:51:16+00	2025-12-04 16:51:16+00
220	Maximum Dosage	100.0000	mg	\N	medium	#E3F2FD	#1565C0	Activity	0	t	\N	2025-12-04 17:19:27+00	2025-12-04 17:19:27+00
221	Low-end Extrapolative Intense Dose	750.0000	mcg	\N	critical	#E3F2FD	#1565C0	Activity	0	t	\N	2025-12-04 18:02:35+00	2025-12-04 18:02:35+00
222	High-end Extrapolative Intense Dose	2000.0000	mcg	\N	critical	#E3F2FD	#1565C0	Activity	0	t	\N	2025-12-04 18:02:58+00	2025-12-04 18:02:58+00
223	Very Low Concentration	0.2000	%	\N	low	#E3F2FD	#1565C0	Activity	0	t	\N	2025-12-04 18:16:21+00	2025-12-04 18:16:21+00
224	Moderate Concentration	0.5000	%	\N	medium	#E3F2FD	#1565C0	Activity	0	t	\N	2025-12-04 18:16:44+00	2025-12-04 18:16:44+00
225	High Concentration	1.0000	%	\N	medium	#E3F2FD	#1565C0	Activity	0	t	\N	2025-12-04 18:16:59+00	2025-12-04 18:20:24+00
226	High-Moderate Dose	4800.0000	mcg	\N	high	#E3F2FD	#1565C0	Activity	0	t	\N	2025-12-04 18:30:45+00	2025-12-04 18:34:05+00
227	Medium Dose	1.0000	mg	\N	medium	#E3F2FD	#1565C0	Activity	0	t	\N	2025-12-04 19:45:38+00	2025-12-04 19:45:38+00
228	Maximum Recommended Dose	1.5000	mg	\N	medium	#E3F2FD	#1565C0	Activity	0	t	\N	2025-12-05 18:36:10+00	2025-12-05 18:36:10+00
229	Low Concentration	2.5000	%	\N	low	#E3F2FD	#1565C0	Activity	0	t	\N	2025-12-13 16:41:15+00	2025-12-13 16:41:15+00
230	Standard Concentration	5.0000	%	\N	low	#E3F2FD	#1565C0	Activity	0	t	\N	2025-12-13 16:41:25+00	2025-12-13 16:41:25+00
231	High Concentration	10.0000	%	\N	high	#E3F2FD	#1565C0	Activity	0	t	\N	2025-12-13 17:15:37+00	2025-12-13 17:15:37+00
232	Minimal Concentration	2.0000	%	\N	low	#E3F2FD	#1565C0	Activity	0	t	\N	2025-12-13 18:00:26+00	2025-12-13 18:00:26+00
233	Enhanced Concentration	5.0000	%	\N	medium	#E3F2FD	#1565C0	Activity	0	t	\N	2025-12-13 18:00:39+00	2025-12-13 18:00:39+00
234	Maximum Concentration	10.0000	%	\N	high	#E3F2FD	#1565C0	Activity	0	t	\N	2025-12-13 18:00:53+00	2025-12-13 18:00:53+00
235	Low Dose	6.2500	mg	\N	low	#E3F2FD	#1565C0	Activity	0	t	\N	2025-12-14 17:47:09+00	2025-12-14 17:47:09+00
236	Standard Dose	12.5000	mg	\N	medium	#E3F2FD	#1565C0	Activity	0	t	\N	2025-12-14 17:47:21+00	2025-12-14 17:47:21+00
237	High Dose	25.0000	mg	\N	medium	#E3F2FD	#1565C0	Activity	0	t	\N	2025-12-14 17:47:29+00	2025-12-14 17:47:29+00
238	Low Concentration	5.0000	%	\N	medium	#E3F2FD	#1565C0	Activity	0	t	\N	2025-12-14 18:06:54+00	2025-12-14 18:06:54+00
239	Medium Dosage	10.0000	%	\N	medium	#E3F2FD	#1565C0	Activity	0	t	\N	2025-12-14 18:07:05+00	2025-12-14 18:07:05+00
240	High Concentration	15.0000	%	\N	medium	#E3F2FD	#1565C0	Activity	0	t	\N	2025-12-14 18:07:14+00	2025-12-14 18:08:29+00
241	Starting Dose	0.3000	mg	\N	low	#E3F2FD	#1565C0	Activity	0	t	\N	2025-12-14 23:45:56+00	2025-12-14 23:45:56+00
242	2nd Escalation	0.6000	mg	\N	medium	#E3F2FD	#1565C0	Activity	0	t	\N	2025-12-14 23:46:34+00	2025-12-14 23:46:34+00
243	3rd Escalation	0.9000	mg	\N	medium	#E3F2FD	#1565C0	Activity	0	t	\N	2025-12-14 23:46:46+00	2025-12-14 23:46:46+00
244	4th Escalation	1.2000	mg	\N	medium	#E3F2FD	#1565C0	Activity	0	t	\N	2025-12-14 23:47:01+00	2025-12-14 23:47:01+00
245	5th Escalation	1.8000	mg	\N	medium	#E3F2FD	#1565C0	Activity	0	t	\N	2025-12-14 23:47:23+00	2025-12-14 23:47:23+00
246	6th Escalation	2.4000	mg	\N	medium	#E3F2FD	#1565C0	Activity	0	t	\N	2025-12-14 23:47:50+00	2025-12-14 23:47:50+00
247	Maximum Escalation	4.5000	mg	\N	medium	#E3F2FD	#1565C0	Activity	0	t	\N	2025-12-14 23:48:12+00	2025-12-14 23:48:12+00
248	Standard Dosage	700.0000	mcg	\N	critical	#E3F2FD	#1565C0	Activity	0	t	\N	2025-12-18 20:36:46+00	2025-12-18 20:36:46+00
249	Maximum Dosage	800.0000	mcg	\N	critical	#E3F2FD	#1565C0	Activity	0	t	\N	2025-12-18 20:36:58+00	2025-12-18 20:36:58+00
250	Low Dose	100.0000	mg	\N	medium	#E3F2FD	#1565C0	Activity	0	t	\N	2025-12-18 23:29:39+00	2025-12-18 23:29:39+00
251	Moderate Dose	200.0000	mg	\N	medium	#E3F2FD	#1565C0	Activity	0	t	\N	2025-12-18 23:29:48+00	2025-12-18 23:29:48+00
252	High Dose	300.0000	mg	\N	high	#E3F2FD	#1565C0	Activity	0	t	\N	2025-12-18 23:29:57+00	2025-12-18 23:29:57+00
253	Starting Dose	2.5000	mg	\N	medium	#E3F2FD	#1565C0	Activity	0	t	\N	2025-12-19 05:14:31+00	2025-12-19 05:14:31+00
254	2nd Escalation	5.0000	mg	\N	medium	#E3F2FD	#1565C0	Activity	0	t	\N	2025-12-19 05:14:55+00	2025-12-19 05:14:55+00
255	3rd Escalation	7.5000	mg	\N	medium	#E3F2FD	#1565C0	Activity	0	t	\N	2025-12-19 05:15:06+00	2025-12-19 05:15:06+00
256	High Dose 4th Escalation	10.0000	mg	\N	medium	#E3F2FD	#1565C0	Activity	0	t	\N	2025-12-19 05:15:20+00	2025-12-19 05:15:20+00
257	High Dose 5th Escalation	12.5000	mg	\N	medium	#E3F2FD	#1565C0	Activity	0	t	\N	2025-12-19 05:15:34+00	2025-12-19 05:15:34+00
258	Maximum Dosage	15.0000	mg	\N	medium	#E3F2FD	#1565C0	Activity	0	t	\N	2025-12-19 05:15:42+00	2025-12-19 05:15:42+00
259	Medium Dosage	30.0000	mg	\N	medium	#E3F2FD	#1565C0	Activity	0	t	\N	2025-12-19 23:53:46+00	2025-12-19 23:53:46+00
\.


--
-- Data for Name: feedback_questions; Type: TABLE DATA; Schema: public; Owner: -
--

COPY public.feedback_questions (id, question_code, question_label, question_type, sort_order, is_active, created_at, updated_at, deleted_at) FROM stdin;
1	was_helpful	Was this helpful?	yes_no	1	t	2026-04-22 18:39:37.282602+00	2026-04-22 18:39:37.282602+00	\N
2	overall_rating	Overall Rating	rating	2	t	2026-04-22 18:39:37.282602+00	2026-04-22 18:39:37.282602+00	\N
3	would_use_again	Would you use this peptide again?	yes_no	3	t	2026-04-22 18:39:37.282602+00	2026-04-22 18:39:37.282602+00	\N
4	ease_of_use	How easy was it to use?	rating	4	t	2026-04-22 18:39:37.282602+00	2026-04-22 18:39:37.282602+00	\N
5	value_for_money	Value for money	rating	5	t	2026-04-22 18:39:37.282602+00	2026-04-22 18:39:37.282602+00	\N
6	results_timeline	How long until you noticed results?	text	6	t	2026-04-22 18:39:37.282602+00	2026-04-22 18:39:37.282602+00	\N
7	quality_perception	Perceived quality of the product	rating	7	t	2026-04-22 18:39:37.282602+00	2026-04-22 18:39:37.282602+00	\N
8	side_effects_severity	Severity of any side effects	scale	8	t	2026-04-22 18:39:37.282602+00	2026-04-22 18:39:37.282602+00	\N
9	recommend_to_friend	Would you recommend to a friend?	nps	9	t	2026-04-22 18:39:37.282602+00	2026-04-22 18:39:37.282602+00	\N
\.


--
-- Data for Name: influencer_profiles; Type: TABLE DATA; Schema: public; Owner: -
--

COPY public.influencer_profiles (id, user_id, display_name, bio, social_links, referral_code, is_active, profile_visibility, created_at, updated_at) FROM stdin;
1	2e34bfb0-482d-48d8-94a7-9f464c0b1f60	\N	\N	\N	\N	t	public	2026-04-23 01:28:32.58654+00	2026-05-02 13:07:02.154+00
\.


--
-- Data for Name: pepti_price_analytics; Type: TABLE DATA; Schema: public; Owner: -
--

COPY public.pepti_price_analytics (id, ip_address, action, peptide_id, vendor_id, promo_code_id, page_url, user_agent, "timestamp") FROM stdin;
\.


--
-- Data for Name: pepti_price_daily_stats; Type: TABLE DATA; Schema: public; Owner: -
--

COPY public.pepti_price_daily_stats (id, peptide_id, date, price_comparisons, vendor_clicks, promo_applied, created_at) FROM stdin;
\.


--
-- Data for Name: pepti_price_newsletter_subscribers; Type: TABLE DATA; Schema: public; Owner: -
--

COPY public.pepti_price_newsletter_subscribers (id, email, source, unsubscribe_token, confirmed_at, unsubscribed_at, created_at) FROM stdin;
\.


--
-- Data for Name: pepti_price_notifications; Type: TABLE DATA; Schema: public; Owner: -
--

COPY public.pepti_price_notifications (id, user_id, type, payload, read_at, created_at) FROM stdin;
\.


--
-- Data for Name: pepti_price_price_history; Type: TABLE DATA; Schema: public; Owner: -
--

COPY public.pepti_price_price_history (id, peptide_id, vendor_id, administration_method_id, dosage_value, dosage_id, original_price_per_mg, original_total_price, status, recorded_at) FROM stdin;
\.


--
-- Data for Name: pepti_price_promo_codes; Type: TABLE DATA; Schema: public; Owner: -
--

COPY public.pepti_price_promo_codes (id, code, discount_percentage, start_time, end_time, is_active, created_at, updated_at) FROM stdin;
\.


--
-- Data for Name: pepti_price_vendor_pricing; Type: TABLE DATA; Schema: public; Owner: -
--

COPY public.pepti_price_vendor_pricing (id, peptide_id, vendor_id, administration_method_id, dosage_value, original_price_per_mg, original_total_price, status, created_at, updated_at, promo_code_id, dosage_id) FROM stdin;
\.


--
-- Data for Name: pepti_price_watchlist; Type: TABLE DATA; Schema: public; Owner: -
--

COPY public.pepti_price_watchlist (id, user_id, peptide_id, created_at) FROM stdin;
\.


--
-- Data for Name: peptide_benefits; Type: TABLE DATA; Schema: public; Owner: -
--

COPY public.peptide_benefits (id, peptide_id, benefit_id, general_potency, general_evidence_level, sort_order, is_active, created_at, updated_at) FROM stdin;
\.


--
-- Data for Name: peptide_interactions; Type: TABLE DATA; Schema: public; Owner: -
--

COPY public.peptide_interactions (id, peptide_id_1, peptide_id_2, peptide_name_2, interaction_type, description, created_at, updated_at, severity, recommendation) FROM stdin;
\.


--
-- Data for Name: peptide_protocol_reconstitution_steps; Type: TABLE DATA; Schema: public; Owner: -
--

COPY public.peptide_protocol_reconstitution_steps (id, protocol_id, step_number, description, created_at, updated_at) FROM stdin;
\.


--
-- Data for Name: peptide_protocols; Type: TABLE DATA; Schema: public; Owner: -
--

COPY public.peptide_protocols (id, peptide_id, administration_method_id, name, description, expectations, quick_start_guide, mechanism_of_action, key_benefits, best_timing, effects_timeline, is_recommended, sort_order, is_active, deleted_at, created_at, updated_at) FROM stdin;
751	141	1	\N	Subcutaneous injection. The most effective & well-documented route.\n	\N	\N	\N	\N	\N	\N	f	0	t	\N	2025-09-08 01:12:59+00	2025-09-08 01:12:59+00
796	143	1	\N	Subcutaneous injection. The most effective & well-documented route.\n	\N	\N	\N	\N	\N	\N	f	0	t	\N	2025-09-08 19:58:33+00	2025-09-08 19:58:33+00
800	146	2	\N	Oral administration. Poor bioavailability, but high ease of use.\n	\N	\N	\N	\N	\N	\N	f	0	t	\N	2025-09-08 20:01:53+00	2025-09-08 20:01:53+00
807	150	2	\N	\N	\N	\N	\N	\N	\N	\N	f	0	t	\N	2025-09-08 20:06:11+00	2025-09-08 20:06:11+00
819	147	2	\N	Oral administration. Poor bioavailability, but high ease of use.\n	\N	\N	\N	\N	\N	\N	f	0	t	\N	2025-09-08 20:14:15+00	2025-09-08 20:14:15+00
824	152	2	\N	Oral administration. Poor bioavailability, but high ease of use.\n	\N	\N	\N	\N	\N	\N	f	0	t	\N	2025-09-09 16:03:09+00	2025-09-09 16:03:09+00
836	160	2	\N	Oral administration. Poor bioavailability, but high ease of use.\n	\N	\N	\N	\N	\N	\N	f	0	t	\N	2025-09-10 05:34:16+00	2025-09-10 05:34:16+00
837	161	2	\N	Oral administration. Poor bioavailability, but high ease of use.\n	\N	\N	\N	\N	\N	\N	f	0	t	\N	2025-09-11 16:35:35+00	2025-09-11 16:35:35+00
840	163	2	\N	Oral administration. Poor bioavailability, but high ease of use.	\N	\N	\N	\N	\N	\N	f	0	t	\N	2025-09-11 17:32:31+00	2025-09-11 17:32:31+00
846	144	1	\N	Intramuscular injection. The most effective & well-documented route.\n	\N	\N	\N	\N	\N	\N	f	0	t	\N	2025-09-16 16:18:41+00	2025-09-16 16:18:41+00
849	164	2	\N	\N	\N	\N	\N	\N	\N	\N	f	0	t	\N	2025-09-17 01:36:50+00	2025-09-17 01:36:50+00
850	159	2	\N	Oral administration. Poor bioavailability, but high ease of use.\n	\N	\N	\N	\N	\N	\N	f	0	t	\N	2025-09-17 01:39:29+00	2025-09-17 01:39:29+00
852	166	2	\N	Oral administration. Poor bioavailability, but high ease of use.\n	\N	\N	\N	\N	\N	\N	f	0	t	\N	2025-09-20 23:37:48+00	2025-09-20 23:37:48+00
853	167	2	\N	Oral administration. Poor bioavailability, but high ease of use.\n	\N	\N	\N	\N	\N	\N	f	0	t	\N	2025-09-20 23:44:02+00	2025-09-20 23:44:02+00
854	168	2	\N	Oral administration. Poor bioavailability, but high ease of use.\n	\N	\N	\N	\N	\N	\N	f	0	t	\N	2025-09-20 23:54:27+00	2025-09-20 23:54:27+00
855	169	2	\N	Oral administration. Poor bioavailability, but high ease of use.\n	\N	\N	\N	\N	\N	\N	f	0	t	\N	2025-09-21 00:01:52+00	2025-09-21 00:01:52+00
856	170	2	\N	Oral administration. Poor bioavailability, but high ease of use.\n	\N	\N	\N	\N	\N	\N	f	0	t	\N	2025-09-21 00:10:12+00	2025-09-21 00:10:12+00
974	132	1	\N	Subcutaneous administration. Most reliable administration method.	\N	\N	\N	\N	\N	\N	f	0	t	\N	2025-09-29 07:34:42+00	2025-09-29 07:34:42+00
975	132	3	\N	Intranasal administration for non-invasive administration with the bonus of high brain concentration.	\N	\N	\N	\N	\N	\N	f	1	t	\N	2025-09-29 07:34:42+00	2025-09-29 07:34:42+00
1034	174	1	\N	Subcutaneous injection.	\N	\N	\N	\N	\N	\N	f	0	t	\N	2025-10-05 11:14:53+00	2025-10-05 11:14:53+00
1043	176	4	\N	\N	\N	\N	\N	\N	\N	\N	f	0	t	\N	2025-10-07 12:13:00+00	2025-10-07 12:13:00+00
1151	116	1	\N	Subcutaneous injection. The only approved method and the most reliable one.	\N	\N	\N	\N	\N	\N	f	0	t	\N	2025-11-02 04:16:00+00	2025-11-02 04:16:00+00
1180	184	2	\N	\N	\N	\N	\N	\N	\N	\N	f	0	t	\N	2025-11-04 18:59:11+00	2025-11-04 18:59:11+00
1194	187	2	\N	\N	\N	\N	\N	\N	\N	\N	f	0	t	\N	2025-11-05 05:45:16+00	2025-11-05 05:45:16+00
1205	192	2	\N	\N	\N	\N	\N	\N	\N	\N	f	0	t	\N	2025-11-06 21:39:17+00	2025-11-06 21:39:17+00
1211	195	2	\N	\N	\N	\N	\N	\N	\N	\N	f	0	t	\N	2025-11-07 03:35:52+00	2025-11-07 03:35:52+00
1221	175	4	\N	\N	\N	\N	\N	\N	\N	\N	f	0	t	\N	2025-11-14 07:52:37+00	2025-11-14 07:52:37+00
1222	175	1	\N	Scalp Injections	\N	\N	\N	\N	\N	\N	f	1	t	\N	2025-11-14 07:52:37+00	2025-11-14 07:52:37+00
1230	199	2	\N	\N	\N	\N	\N	\N	\N	\N	f	0	t	\N	2025-11-16 02:49:22+00	2025-11-16 02:49:22+00
1247	137	1	\N	Intramuscular injection. The most effective & well-documented route.	\N	\N	\N	\N	\N	\N	f	0	t	\N	2025-11-18 04:03:47+00	2025-11-18 04:03:47+00
1248	137	3	\N	\N	\N	\N	\N	\N	\N	\N	f	1	t	\N	2025-11-18 04:03:47+00	2025-11-18 04:03:47+00
1271	182	1	\N	\N	\N	\N	\N	\N	\N	\N	f	0	t	\N	2025-11-18 11:08:14+00	2025-11-18 11:08:14+00
1272	182	2	\N	\N	\N	\N	\N	\N	\N	\N	f	1	t	\N	2025-11-18 11:08:14+00	2025-11-18 11:08:14+00
1295	190	2	\N	\N	\N	\N	\N	\N	\N	\N	f	0	t	\N	2025-11-29 11:36:41+00	2025-11-29 11:36:41+00
1299	194	2	\N	\N	\N	\N	\N	\N	\N	\N	f	0	t	\N	2025-11-29 12:10:25+00	2025-11-29 12:10:25+00
1313	196	2	\N	\N	\N	\N	\N	\N	\N	\N	f	0	t	\N	2025-11-29 14:58:57+00	2025-11-29 14:58:57+00
1314	198	2	\N	\N	\N	\N	\N	\N	\N	\N	f	0	t	\N	2025-11-29 15:01:51+00	2025-11-29 15:01:51+00
1319	142	2	\N	Subcutaneous injection. The most effective & well-documented route.\n	\N	\N	\N	\N	\N	\N	f	0	t	\N	2025-11-29 15:19:19+00	2025-11-29 15:19:19+00
1335	153	1	\N	Subcutaneous injection. The most effective & well-documented route.\nNo side-effect data available, however selectivity for mTORC2 inhibition should spare it from majority of side effects present in Rapalogs.	\N	\N	\N	\N	\N	\N	f	0	t	\N	2025-12-04 17:40:00+00	2025-12-04 17:40:00+00
1346	162	1	\N	\N	\N	\N	\N	\N	\N	\N	f	0	t	\N	2025-12-04 18:47:23+00	2025-12-04 18:47:23+00
1404	204	2	\N	\N	\N	\N	\N	\N	\N	\N	f	0	t	\N	2025-12-14 17:51:31+00	2025-12-14 17:51:31+00
1415	210	1	\N	This is only effective for unclosed growth plates.	\N	\N	\N	\N	\N	\N	f	0	t	\N	2025-12-18 20:41:49+00	2025-12-18 20:41:49+00
1419	211	2	\N	\N	\N	\N	\N	\N	\N	\N	f	0	t	\N	2025-12-18 23:39:55+00	2025-12-18 23:39:55+00
1421	212	2	\N	\N	\N	\N	\N	\N	\N	\N	f	0	t	\N	2025-12-19 00:17:45+00	2025-12-19 00:17:45+00
1425	213	1	\N	\N	\N	\N	\N	\N	\N	\N	f	0	t	\N	2025-12-19 23:23:05+00	2025-12-19 23:23:05+00
1428	214	2	\N	\N	\N	\N	\N	\N	\N	\N	f	0	t	\N	2025-12-19 23:59:41+00	2025-12-19 23:59:41+00
1431	215	2	\N	\N	\N	\N	\N	\N	\N	\N	f	0	t	\N	2025-12-21 01:02:09+00	2025-12-21 01:02:09+00
1567	217	2	\N	\N	\N	\N	\N	\N	\N	\N	f	0	t	\N	2026-01-16 23:34:16+00	2026-01-16 23:34:16+00
1586	197	4	\N	\N	\N	\N	\N	\N	\N	\N	f	0	t	\N	2026-01-24 04:39:42+00	2026-01-24 04:39:42+00
1611	183	2	\N	\N	\N	\N	\N	\N	\N	\N	f	0	t	\N	2026-02-05 19:30:37+00	2026-02-05 19:30:37+00
1623	117	1	\N	Subcutaneous injection. Only advisable method of administration.	\N	\N	\N	\N	\N	\N	f	0	t	\N	2026-02-06 00:22:09+00	2026-02-06 00:22:09+00
1624	216	1	\N	\N	\N	\N	\N	\N	\N	\N	f	0	t	\N	2026-02-06 00:22:55+00	2026-02-06 00:22:55+00
1625	133	1	\N	Subcutaneous Administration. Most researched and reliable route.	\N	\N	\N	\N	\N	\N	f	0	t	\N	2026-02-06 00:23:53+00	2026-02-06 00:23:53+00
1626	133	3	\N	Intranasal administration. Non-Invasive route with bonus of higher brain concentration.	\N	\N	\N	\N	\N	\N	f	1	t	\N	2026-02-06 00:23:53+00	2026-02-06 00:23:53+00
1628	107	1	Subcutaneous injection	SubQ injection for slow release.	\N	\N	\N	\N	\N	\N	f	0	t	\N	2026-02-06 00:24:33+00	2026-02-06 00:24:33+00
1629	107	3	Intranasal administration.	Non-Invasive approach with high bioavailability and reaches higher brain concentration.	\N	\N	\N	\N	\N	\N	f	1	t	\N	2026-02-06 00:24:33+00	2026-02-06 00:24:33+00
1630	125	1	\N	Subcutaneous administration. Due to the inherent risks of this peptide lowest effective dose is necessary. Adjust cycle duration according collagenous tissue response as it inherently degrades collagenous tissues systemically. Taking time off if something feels off is preferred over mindlessly degrading cartilage, skin, tendon and ligament tissues.\n\nDosages below are purely from scarce anectodal evidence due to lack of substancial research for human use. Handle usage with utmost care.	\N	\N	\N	\N	\N	\N	f	0	t	\N	2026-02-06 00:24:51+00	2026-02-06 00:24:51+00
1634	148	1	\N	Subcutaneous injection. The most effective & well-documented route.\n	\N	\N	\N	\N	\N	\N	f	0	t	\N	2026-02-06 00:26:49+00	2026-02-06 00:26:49+00
1635	148	2	\N	\N	\N	\N	\N	\N	\N	\N	f	1	t	\N	2026-02-06 00:26:49+00	2026-02-06 00:26:49+00
1636	208	1	\N	\N	\N	\N	\N	\N	\N	\N	f	0	t	\N	2026-02-06 00:27:10+00	2026-02-06 00:27:10+00
1637	201	4	\N	\N	\N	\N	\N	\N	\N	\N	f	0	t	\N	2026-02-06 00:27:33+00	2026-02-06 00:27:33+00
1638	181	1	\N	Intramuscular or IV administration.	\N	\N	\N	\N	\N	\N	f	0	t	\N	2026-02-06 00:27:51+00	2026-02-06 00:27:51+00
1639	151	2	\N	\N	\N	\N	\N	\N	\N	\N	f	0	t	\N	2026-02-06 00:28:06+00	2026-02-06 00:28:06+00
1640	151	1	\N	Subcutaneous injection. The most effective & well-documented route.\n	\N	\N	\N	\N	\N	\N	f	1	t	\N	2026-02-06 00:28:06+00	2026-02-06 00:28:06+00
1644	145	2	\N	Oral administration. Poor bioavailability, but high ease of use.\n	\N	\N	\N	\N	\N	\N	f	0	t	\N	2026-02-06 00:31:07+00	2026-02-06 00:31:07+00
1645	145	1	\N	Subcutaneous or intramuscular injection. The most effective & well-documented route.\n	\N	\N	\N	\N	\N	\N	f	1	t	\N	2026-02-06 00:31:07+00	2026-02-06 00:31:07+00
1648	207	1	\N	\N	\N	\N	\N	\N	\N	\N	f	0	t	\N	2026-02-06 00:31:49+00	2026-02-06 00:31:49+00
1651	134	1	\N	Subcutaneous injection. The most effective & well-documented route.	\N	\N	\N	\N	\N	\N	f	0	t	\N	2026-02-06 00:32:45+00	2026-02-06 00:32:45+00
1652	134	3	\N	Intranasal administration. Non-invasive and provides rapid delivery to the CNS via the olfactory pathway for a higher brain concentration.\n	\N	\N	\N	\N	\N	\N	f	1	t	\N	2026-02-06 00:32:45+00	2026-02-06 00:32:45+00
1653	134	4	\N	Topical cream administration. Ideal for skin aging / local regeneration purposes.	\N	\N	\N	\N	\N	\N	f	2	t	\N	2026-02-06 00:32:45+00	2026-02-06 00:32:45+00
1654	177	1	\N	\N	\N	\N	\N	\N	\N	\N	f	0	t	\N	2026-02-06 00:33:00+00	2026-02-06 00:33:00+00
1655	177	3	\N	\N	\N	\N	\N	\N	\N	\N	f	1	t	\N	2026-02-06 00:33:00+00	2026-02-06 00:33:00+00
1656	156	1	\N	Subcutaneous injection. The most effective & well-documented route.\n	\N	\N	\N	\N	\N	\N	f	0	t	\N	2026-02-06 00:33:16+00	2026-02-06 00:33:16+00
1657	124	1	\N	Subcutaneous administration.	\N	\N	\N	\N	\N	\N	f	0	t	\N	2026-02-06 00:33:33+00	2026-02-06 00:33:33+00
1666	200	1	\N	\N	\N	\N	\N	\N	\N	\N	f	0	t	\N	2026-02-06 00:36:47+00	2026-02-06 00:36:47+00
1672	206	1	\N	\N	\N	\N	\N	\N	\N	\N	f	0	t	\N	2026-02-06 00:39:43+00	2026-02-06 00:39:43+00
1679	140	3	\N	Intranasal administration. Non-invasive and provides rapid delivery to the CNS via the olfactory pathway for a higher brain concentration.\n	\N	\N	\N	\N	\N	\N	f	0	t	\N	2026-02-06 00:40:51+00	2026-02-06 00:40:51+00
1680	140	1	\N	\N	\N	\N	\N	\N	\N	\N	f	1	t	\N	2026-02-06 00:40:51+00	2026-02-06 00:40:51+00
1681	103	1	SubQ Injection	Subcutaneous injection for Immunomodulation.	\N	\N	\N	\N	\N	\N	f	0	t	\N	2026-02-06 00:41:06+00	2026-02-06 00:41:06+00
1682	103	4	Wound Care	\N	\N	\N	\N	\N	\N	\N	f	1	t	\N	2026-02-06 00:41:06+00	2026-02-06 00:41:06+00
1683	127	1	\N	Weekly subcutaneous administration. Titration necessary.	\N	\N	\N	\N	\N	\N	f	0	t	\N	2026-02-06 00:41:34+00	2026-02-06 00:41:34+00
1687	188	2	\N	\N	\N	\N	\N	\N	\N	\N	f	0	t	\N	2026-02-06 00:44:05+00	2026-02-06 00:44:05+00
1691	114	1	Subcutaneous administration.	Subcutaneous injection for high bioavailability and extended release. 	\N	\N	\N	\N	\N	\N	f	0	t	\N	2026-02-06 00:46:11+00	2026-02-06 00:46:11+00
1692	114	3	Intranasal administration.	Intranasal administration for higher brain concentration and a non-invasive approach for higher bioavailability.	\N	\N	\N	\N	\N	\N	f	1	t	\N	2026-02-06 00:46:11+00	2026-02-06 00:46:11+00
1693	114	4	\N	\N	\N	\N	\N	\N	\N	\N	f	2	t	\N	2026-02-06 00:46:11+00	2026-02-06 00:46:11+00
1696	165	2	\N	Oral administration. Poor bioavailability, but high ease of use.	\N	\N	\N	\N	\N	\N	f	0	t	\N	2026-02-06 00:47:06+00	2026-02-06 00:47:06+00
1699	106	1	Subcutaneous Administration	Subcutaneous administration for systemic effects.	\N	\N	\N	\N	\N	\N	f	0	t	\N	2026-02-06 01:03:18+00	2026-02-06 01:03:18+00
1700	106	3	Intranasal administration.	A non-invasive approach for high bioavailability and high concentration in the brain.	\N	\N	\N	\N	\N	\N	f	1	t	\N	2026-02-06 01:03:18+00	2026-02-06 01:03:18+00
1701	149	2	\N	Oral administration. Poor bioavailability, but high ease of use.\n	\N	\N	\N	\N	\N	\N	f	0	t	\N	2026-02-06 01:03:35+00	2026-02-06 01:03:35+00
1702	149	1	\N	Subcutaneous injection. The most effective & well-documented route.\n	\N	\N	\N	\N	\N	\N	f	1	t	\N	2026-02-06 01:03:35+00	2026-02-06 01:03:35+00
1703	118	1	\N	Subcutaneous injection. Most reliable and bioavailable route.	\N	\N	\N	\N	\N	\N	f	0	t	\N	2026-02-06 01:03:49+00	2026-02-06 01:03:49+00
1704	118	3	\N	Intranasal administration. Non-invasive alternative with high bioavailability.	\N	\N	\N	\N	\N	\N	f	1	t	\N	2026-02-06 01:03:49+00	2026-02-06 01:03:49+00
1706	135	3	\N	Intranasal administration. Non-invasive and provides rapid delivery to the CNS via the olfactory pathway for a higher brain concentration.\n	\N	\N	\N	\N	\N	\N	f	0	t	\N	2026-02-06 01:04:29+00	2026-02-06 01:04:29+00
1707	119	1	\N	Subcutaneous administration for slow release and high bioavailability. Morning administration.	\N	\N	\N	\N	\N	\N	f	0	t	\N	2026-02-06 01:04:58+00	2026-02-06 01:04:58+00
1714	205	4	\N	\N	\N	\N	\N	\N	\N	\N	f	0	t	\N	2026-02-06 01:06:32+00	2026-02-06 01:06:32+00
1715	129	1	\N	Once weekly subcutaneous injection.	\N	\N	\N	\N	\N	\N	f	0	t	\N	2026-02-06 01:06:45+00	2026-02-06 01:06:45+00
1718	209	1	\N	\N	\N	\N	\N	\N	\N	\N	f	0	t	\N	2026-02-06 01:07:35+00	2026-02-06 01:07:35+00
1719	138	1	\N	Subcutaneous injection. The most effective & well-documented route.\n	\N	\N	\N	\N	\N	\N	f	0	t	\N	2026-02-06 01:07:57+00	2026-02-06 01:07:57+00
1720	138	3	\N	Intranasal administration. Non-invasive and provides rapid delivery to the CNS via the olfactory pathway for a higher brain concentration.\n	\N	\N	\N	\N	\N	\N	f	1	t	\N	2026-02-06 01:07:58+00	2026-02-06 01:07:58+00
1721	130	1	\N	\N	\N	\N	\N	\N	\N	\N	f	0	t	\N	2026-02-06 01:08:11+00	2026-02-06 01:08:11+00
1722	203	4	\N	\N	\N	\N	\N	\N	\N	\N	f	0	t	\N	2026-02-06 01:08:23+00	2026-02-06 01:08:23+00
1723	136	2	\N	\N	\N	\N	\N	\N	\N	\N	f	0	t	\N	2026-02-06 01:08:35+00	2026-02-06 01:08:35+00
1724	136	1	\N	\N	\N	\N	\N	\N	\N	\N	f	1	t	\N	2026-02-06 01:08:35+00	2026-02-06 01:08:35+00
1725	139	1	\N	Subcutaneous injection. The most effective & well-documented route.\n	\N	\N	\N	\N	\N	\N	f	0	t	\N	2026-02-06 01:08:45+00	2026-02-06 01:08:45+00
1726	139	3	\N	Intranasal administration. Non-invasive and provides rapid delivery to the CNS via the olfactory pathway for a higher brain concentration.\n	\N	\N	\N	\N	\N	\N	f	1	t	\N	2026-02-06 01:08:45+00	2026-02-06 01:08:45+00
1730	23	1	Weight Loss Protocol	Weekly subcutaneous injection for weight management	\N	\N	\N	\N	\N	\N	t	0	t	\N	2026-02-18 22:17:33+00	2026-02-18 22:17:33+00
1731	113	2	Oral	\N	\N	\N	\N	\N	\N	\N	f	0	t	\N	2026-02-18 22:18:28+00	2026-02-18 22:18:28+00
1732	113	1	Subcutaneous Administration	Subcutaneous injection. Useful for better bioavailability, extended release.	\N	\N	\N	\N	\N	\N	f	1	t	\N	2026-02-18 22:18:28+00	2026-02-18 22:18:28+00
1733	115	1	\N	Subcutaneous injection. Most reliable and bioavailable. 	\N	\N	\N	\N	\N	\N	f	0	t	\N	2026-02-18 22:21:10+00	2026-02-18 22:21:10+00
1734	100	1	\N	SubQ or IM Injection. The most effective & well-documented route.\n	\N	\N	\N	\N	\N	\N	f	0	t	\N	2026-02-18 22:26:35+00	2026-02-18 22:26:35+00
1735	100	2	Oral	Oral administration for IBS, Ulcers, Hiatal hernias.	\N	\N	\N	\N	\N	\N	f	1	t	\N	2026-02-18 22:26:35+00	2026-02-18 22:26:35+00
1736	100	4	\N	Topical cream administration. Ideal for skin aging / local regeneration goals.\n	\N	\N	\N	\N	\N	\N	f	2	t	\N	2026-02-18 22:26:35+00	2026-02-18 22:26:35+00
1737	186	3	\N	\N	\N	\N	\N	\N	\N	\N	f	0	t	\N	2026-02-18 22:28:25+00	2026-02-18 22:28:25+00
1738	186	2	\N	\N	\N	\N	\N	\N	\N	\N	f	1	t	\N	2026-02-18 22:28:25+00	2026-02-18 22:28:25+00
1740	26	1	Extended Release Protocol	Weekly subcutaneous injection for sustained GH release	\N	\N	\N	\N	\N	\N	t	0	t	\N	2026-02-18 22:33:54+00	2026-02-18 22:33:54+00
1741	120	1	\N	Subcutaneous injection for slow release and maximum bioavailability.	\N	\N	\N	\N	\N	\N	f	0	t	\N	2026-02-18 22:34:16+00	2026-02-18 22:34:16+00
1742	105	2	Oral	Most common route. Taken on an empty stomach.	\N	\N	\N	\N	\N	\N	f	0	t	\N	2026-02-18 22:35:08+00	2026-02-18 22:35:08+00
1743	105	3	Intranasal Administration	Preferrable administration method. Has better bioavailability and reaches higher concentration in the brain.	\N	\N	\N	\N	\N	\N	f	1	t	\N	2026-02-18 22:35:08+00	2026-02-18 22:35:08+00
1744	27	1	Injectable Sleep Protocol	Subcutaneous injection before bedtime for sleep improvement	\N	\N	\N	\N	\N	\N	t	0	t	\N	2026-02-18 22:36:07+00	2026-02-18 22:36:07+00
1745	27	3	Nasal Spray Protocol	Intranasal administration for sleep enhancement	\N	\N	\N	\N	\N	\N	f	1	t	\N	2026-02-18 22:36:07+00	2026-02-18 22:36:07+00
1746	104	1	Subcutaneous Injection	\N	\N	\N	\N	\N	\N	\N	f	0	t	\N	2026-02-18 22:38:36+00	2026-02-18 22:38:36+00
1747	104	4	Topical Administration	\N	\N	\N	\N	\N	\N	\N	f	1	t	\N	2026-02-18 22:38:36+00	2026-02-18 22:38:36+00
1748	122	1	\N	Subcutaneous administration. Only recommendable route of administration due to bioavailability. Oral and intranasal are possible but extremely inefficient.	\N	\N	\N	\N	\N	\N	f	0	t	\N	2026-02-18 22:39:09+00	2026-02-18 22:39:09+00
1749	121	1	\N	Subcutaneous administration. Only recommended administration due to poor bioavailability with other routes.	\N	\N	\N	\N	\N	\N	f	0	t	\N	2026-02-18 22:39:42+00	2026-02-18 22:39:42+00
1750	189	2	\N	\N	\N	\N	\N	\N	\N	\N	f	0	t	\N	2026-02-18 22:40:14+00	2026-02-18 22:40:14+00
1751	19	1	Testosterone Support Protocol	Intramuscular injection for testosterone production and fertility	\N	\N	\N	\N	\N	\N	t	0	t	\N	2026-02-18 22:40:45+00	2026-02-18 22:40:45+00
1752	173	1	\N	Subcutaneous injection. Only advisable method of administration.	\N	\N	\N	\N	\N	\N	f	0	t	\N	2026-02-18 22:41:16+00	2026-02-18 22:41:16+00
1753	155	1	\N	Subcutaneous injection. The most effective & well-documented route.\n	\N	\N	\N	\N	\N	\N	f	0	t	\N	2026-02-18 22:42:10+00	2026-02-18 22:42:10+00
1754	131	1	\N	Subcutaneous administration for hormone production or treatment for intertility.	\N	\N	\N	\N	\N	\N	f	0	t	\N	2026-02-18 22:42:40+00	2026-02-18 22:42:40+00
1755	128	1	\N	Subcutaneous injection. Intended for localized effects.	\N	\N	\N	\N	\N	\N	f	0	t	\N	2026-02-18 22:43:25+00	2026-02-18 22:43:25+00
1756	128	3	\N	Intranasal administration for non-invasive administration intended for neurological benefits. 	\N	\N	\N	\N	\N	\N	f	1	t	\N	2026-02-18 22:43:25+00	2026-02-18 22:43:25+00
1757	112	1	Subcutaneous Administration	Subcutaneous injection. Morning Administration.	\N	\N	\N	\N	\N	\N	f	0	t	\N	2026-02-18 22:43:54+00	2026-02-18 22:43:54+00
1758	112	3	Intranasal Administration	Non-Invasive approach for administration. Higher concentration in the brain.	\N	\N	\N	\N	\N	\N	f	1	t	\N	2026-02-18 22:43:54+00	2026-02-18 22:43:54+00
1759	25	1	Growth Hormone Protocol	Subcutaneous injection for GH release, preferably before bed	\N	\N	\N	\N	\N	\N	t	0	t	\N	2026-02-18 22:44:56+00	2026-02-18 22:44:56+00
1760	4	1	Anti-inflammatory Protocol	Injectable protocol for systemic anti-inflammatory effects	\N	\N	\N	\N	\N	\N	t	0	t	\N	2026-02-18 22:45:43+00	2026-02-18 22:45:43+00
1761	4	2	Oral Protocol	Oral administration for IBD and digestive inflammation	\N	\N	\N	\N	\N	\N	t	1	t	\N	2026-02-18 22:45:43+00	2026-02-18 22:45:43+00
1762	4	4	Topical Protocol	Direct application for localized inflammation and skin conditions	\N	\N	\N	\N	\N	\N	t	2	t	\N	2026-02-18 22:45:43+00	2026-02-18 22:45:43+00
1763	4	3	\N	Intranasal protocol.	\N	\N	\N	\N	\N	\N	f	3	t	\N	2026-02-18 22:45:43+00	2026-02-18 22:45:43+00
1764	20	1	IV/Injectable Protocol	Intravenous or subcutaneous for maximum bioavailability	\N	\N	\N	\N	\N	\N	t	0	t	\N	2026-02-18 22:46:25+00	2026-02-18 22:46:25+00
1765	20	2	Oral Supplement Protocol	Oral administration for convenience and daily use	\N	\N	\N	\N	\N	\N	f	1	t	\N	2026-02-18 22:46:25+00	2026-02-18 22:46:25+00
1766	180	1	\N	\N	\N	\N	\N	\N	\N	\N	f	0	t	\N	2026-02-18 22:47:02+00	2026-02-18 22:47:02+00
1767	3	1	Tanning Protocol	Subcutaneous injection for melanogenesis and sexual enhancement	\N	\N	\N	\N	\N	\N	t	0	t	\N	2026-02-18 22:47:28+00	2026-02-18 22:47:28+00
1768	3	3	Nasal Spray Protocol	Intranasal administration for convenient dosing	\N	\N	\N	\N	\N	\N	f	1	t	\N	2026-02-18 22:47:28+00	2026-02-18 22:47:28+00
1769	178	2	\N	\N	\N	\N	\N	\N	\N	\N	f	0	t	\N	2026-02-18 22:48:30+00	2026-02-18 22:48:30+00
1770	191	2	\N	\N	\N	\N	\N	\N	\N	\N	f	0	t	\N	2026-02-18 22:49:04+00	2026-02-18 22:49:04+00
1771	126	1	\N	Subcutaneous administration every morning.	\N	\N	\N	\N	\N	\N	f	0	t	\N	2026-02-18 22:49:33+00	2026-02-18 22:49:33+00
1772	126	3	\N	Intranasal administration for a non-invasive approach for administration, alongside providing higher brain concentrations than injections.	\N	\N	\N	\N	\N	\N	f	1	t	\N	2026-02-18 22:49:33+00	2026-02-18 22:49:33+00
1773	158	1	\N	\N	\N	\N	\N	\N	\N	\N	f	0	t	\N	2026-02-18 22:50:10+00	2026-02-18 22:50:10+00
1774	158	3	\N	\N	\N	\N	\N	\N	\N	\N	f	1	t	\N	2026-02-18 22:50:10+00	2026-02-18 22:50:10+00
1775	185	2	\N	\N	\N	\N	\N	\N	\N	\N	f	0	t	\N	2026-02-18 22:50:44+00	2026-02-18 22:50:44+00
1776	18	1	\N	\N	\N	\N	\N	\N	\N	\N	f	0	t	\N	2026-02-18 22:51:11+00	2026-02-18 22:51:11+00
1777	18	3	\N	\N	\N	\N	\N	\N	\N	\N	f	1	t	\N	2026-02-18 22:51:11+00	2026-02-18 22:51:11+00
1778	123	1	\N	Subcutaneous injection.	\N	\N	\N	\N	\N	\N	f	0	t	\N	2026-02-18 22:51:39+00	2026-02-18 22:51:39+00
1779	193	2	\N	\N	\N	\N	\N	\N	\N	\N	f	0	t	\N	2026-02-18 22:52:05+00	2026-02-18 22:52:05+00
1780	22	1	Libido Enhancement Protocol	Subcutaneous injection for sexual dysfunction treatment	\N	\N	\N	\N	\N	\N	t	0	t	\N	2026-02-18 22:52:42+00	2026-02-18 22:52:42+00
1781	22	3	Nasal Spray Protocol	Intranasal administration for convenience	\N	\N	\N	\N	\N	\N	f	1	t	\N	2026-02-18 22:52:42+00	2026-02-18 22:52:42+00
1782	202	4	\N	\N	\N	\N	\N	\N	\N	\N	f	0	t	\N	2026-02-18 22:53:19+00	2026-02-18 22:53:19+00
1783	24	1	Injectable Protocol	Subcutaneous injection for anxiety and cognitive enhancement	\N	\N	\N	\N	\N	\N	f	0	t	\N	2026-02-18 22:53:50+00	2026-02-18 22:53:50+00
1784	24	3	Nasal Spray Protocol	Intranasal administration for anxiety relief	\N	\N	\N	\N	\N	\N	t	1	t	\N	2026-02-18 22:53:50+00	2026-02-18 22:53:50+00
1785	21	3	Nasal Spray Protocol	Intranasal administration for direct brain delivery	\N	\N	\N	\N	\N	\N	t	0	t	\N	2026-02-18 22:54:25+00	2026-02-18 22:54:25+00
1786	2	1	\N	\N	\N	\N	\N	\N	\N	\N	f	0	t	\N	2026-02-18 22:54:56+00	2026-02-18 22:54:56+00
1787	102	1	SubQ Injection	Subcutaneous injection for GH release, preferably before bed.\n	\N	\N	\N	\N	\N	\N	f	0	t	\N	2026-02-18 22:55:46+00	2026-02-18 22:55:46+00
1788	157	1	\N	Subcutaneous injection. The most effective & well-documented route.\n	\N	\N	\N	\N	\N	\N	f	0	t	\N	2026-02-18 22:56:14+00	2026-02-18 22:56:14+00
1789	157	3	\N	Intranasal administration. Non-invasive and provides rapid delivery to the CNS via the olfactory pathway for a higher brain concentration.\n	\N	\N	\N	\N	\N	\N	f	1	t	\N	2026-02-18 22:56:14+00	2026-02-18 22:56:14+00
\.


--
-- Data for Name: peptide_question_assignments; Type: TABLE DATA; Schema: public; Owner: -
--

COPY public.peptide_question_assignments (id, peptide_id, question_id, sort_order, is_active, created_at, updated_at) FROM stdin;
\.


--
-- Data for Name: peptide_question_option_assignments; Type: TABLE DATA; Schema: public; Owner: -
--

COPY public.peptide_question_option_assignments (id, question_id, question_option_id, sort_order, is_active, created_at, updated_at) FROM stdin;
1	1	14	1	t	2026-04-22 18:39:27.229156+00	2026-04-22 18:39:27.229156+00
2	1	56	2	t	2026-04-22 18:39:27.229156+00	2026-04-22 18:39:27.229156+00
3	1	46	3	t	2026-04-22 18:39:27.229156+00	2026-04-22 18:39:27.229156+00
4	1	29	4	t	2026-04-22 18:39:27.229156+00	2026-04-22 18:39:27.229156+00
5	1	44	5	t	2026-04-22 18:39:27.229156+00	2026-04-22 18:39:27.229156+00
6	2	30	1	t	2026-04-22 18:39:27.229156+00	2026-04-22 18:39:27.229156+00
7	2	1	2	t	2026-04-22 18:39:27.229156+00	2026-04-22 18:39:27.229156+00
8	2	5	3	t	2026-04-22 18:39:27.229156+00	2026-04-22 18:39:27.229156+00
9	2	9	4	t	2026-04-22 18:39:27.229156+00	2026-04-22 18:39:27.229156+00
10	2	45	5	t	2026-04-22 18:39:27.229156+00	2026-04-22 18:39:27.229156+00
11	2	37	6	t	2026-04-22 18:39:27.229156+00	2026-04-22 18:39:27.229156+00
12	2	44	7	t	2026-04-22 18:39:27.229156+00	2026-04-22 18:39:27.229156+00
13	3	2	1	t	2026-04-22 18:39:27.229156+00	2026-04-22 18:39:27.229156+00
14	3	4	2	t	2026-04-22 18:39:27.229156+00	2026-04-22 18:39:27.229156+00
15	3	6	3	t	2026-04-22 18:39:27.229156+00	2026-04-22 18:39:27.229156+00
16	3	7	4	t	2026-04-22 18:39:27.229156+00	2026-04-22 18:39:27.229156+00
17	3	8	5	t	2026-04-22 18:39:27.229156+00	2026-04-22 18:39:27.229156+00
18	3	10	6	t	2026-04-22 18:39:27.229156+00	2026-04-22 18:39:27.229156+00
19	3	47	7	t	2026-04-22 18:39:27.229156+00	2026-04-22 18:39:27.229156+00
20	4	31	1	t	2026-04-22 18:39:27.229156+00	2026-04-22 18:39:27.229156+00
21	4	21	2	t	2026-04-22 18:39:27.229156+00	2026-04-22 18:39:27.229156+00
22	4	36	3	t	2026-04-22 18:39:27.229156+00	2026-04-22 18:39:27.229156+00
23	4	47	4	t	2026-04-22 18:39:27.229156+00	2026-04-22 18:39:27.229156+00
24	4	44	5	t	2026-04-22 18:39:27.229156+00	2026-04-22 18:39:27.229156+00
25	5	32	1	t	2026-04-22 18:39:27.229156+00	2026-04-22 18:39:27.229156+00
26	5	19	2	t	2026-04-22 18:39:27.229156+00	2026-04-22 18:39:27.229156+00
27	5	50	3	t	2026-04-22 18:39:27.229156+00	2026-04-22 18:39:27.229156+00
28	5	11	4	t	2026-04-22 18:39:27.229156+00	2026-04-22 18:39:27.229156+00
29	5	13	5	t	2026-04-22 18:39:27.229156+00	2026-04-22 18:39:27.229156+00
30	5	23	6	t	2026-04-22 18:39:27.229156+00	2026-04-22 18:39:27.229156+00
31	5	44	7	t	2026-04-22 18:39:27.229156+00	2026-04-22 18:39:27.229156+00
32	6	57	1	t	2026-04-22 18:39:27.229156+00	2026-04-22 18:39:27.229156+00
33	6	53	2	t	2026-04-22 18:39:27.229156+00	2026-04-22 18:39:27.229156+00
34	6	34	3	t	2026-04-22 18:39:27.229156+00	2026-04-22 18:39:27.229156+00
35	6	40	4	t	2026-04-22 18:39:27.229156+00	2026-04-22 18:39:27.229156+00
36	6	38	5	t	2026-04-22 18:39:27.229156+00	2026-04-22 18:39:27.229156+00
37	6	54	6	t	2026-04-22 18:39:27.229156+00	2026-04-22 18:39:27.229156+00
38	6	44	7	t	2026-04-22 18:39:27.229156+00	2026-04-22 18:39:27.229156+00
39	7	24	1	t	2026-04-22 18:39:27.229156+00	2026-04-22 18:39:27.229156+00
40	7	33	2	t	2026-04-22 18:39:27.229156+00	2026-04-22 18:39:27.229156+00
41	7	20	3	t	2026-04-22 18:39:27.229156+00	2026-04-22 18:39:27.229156+00
42	7	26	4	t	2026-04-22 18:39:27.229156+00	2026-04-22 18:39:27.229156+00
43	7	17	5	t	2026-04-22 18:39:27.229156+00	2026-04-22 18:39:27.229156+00
44	7	27	6	t	2026-04-22 18:39:27.229156+00	2026-04-22 18:39:27.229156+00
45	7	58	7	t	2026-04-22 18:39:27.229156+00	2026-04-22 18:39:27.229156+00
46	7	28	8	t	2026-04-22 18:39:27.229156+00	2026-04-22 18:39:27.229156+00
47	7	35	9	t	2026-04-22 18:39:27.229156+00	2026-04-22 18:39:27.229156+00
48	7	44	10	t	2026-04-22 18:39:27.229156+00	2026-04-22 18:39:27.229156+00
49	8	41	1	t	2026-04-22 18:39:27.229156+00	2026-04-22 18:39:27.229156+00
50	8	55	2	t	2026-04-22 18:39:27.229156+00	2026-04-22 18:39:27.229156+00
51	8	18	3	t	2026-04-22 18:39:27.229156+00	2026-04-22 18:39:27.229156+00
52	8	3	4	t	2026-04-22 18:39:27.229156+00	2026-04-22 18:39:27.229156+00
53	8	42	5	t	2026-04-22 18:39:27.229156+00	2026-04-22 18:39:27.229156+00
54	8	12	6	t	2026-04-22 18:39:27.229156+00	2026-04-22 18:39:27.229156+00
55	8	37	7	t	2026-04-22 18:39:27.229156+00	2026-04-22 18:39:27.229156+00
56	8	44	8	t	2026-04-22 18:39:27.229156+00	2026-04-22 18:39:27.229156+00
57	9	16	1	t	2026-04-22 18:39:27.229156+00	2026-04-22 18:39:27.229156+00
58	9	49	2	t	2026-04-22 18:39:27.229156+00	2026-04-22 18:39:27.229156+00
59	9	39	3	t	2026-04-22 18:39:27.229156+00	2026-04-22 18:39:27.229156+00
60	9	48	4	t	2026-04-22 18:39:27.229156+00	2026-04-22 18:39:27.229156+00
61	9	15	5	t	2026-04-22 18:39:27.229156+00	2026-04-22 18:39:27.229156+00
62	9	44	6	t	2026-04-22 18:39:27.229156+00	2026-04-22 18:39:27.229156+00
63	10	52	1	t	2026-04-22 18:39:27.229156+00	2026-04-22 18:39:27.229156+00
64	10	51	2	t	2026-04-22 18:39:27.229156+00	2026-04-22 18:39:27.229156+00
65	10	25	3	t	2026-04-22 18:39:27.229156+00	2026-04-22 18:39:27.229156+00
66	10	22	4	t	2026-04-22 18:39:27.229156+00	2026-04-22 18:39:27.229156+00
67	10	43	5	t	2026-04-22 18:39:27.229156+00	2026-04-22 18:39:27.229156+00
68	10	59	6	t	2026-04-22 18:39:27.229156+00	2026-04-22 18:39:27.229156+00
69	10	44	7	t	2026-04-22 18:39:27.229156+00	2026-04-22 18:39:27.229156+00
\.


--
-- Data for Name: peptide_question_options; Type: TABLE DATA; Schema: public; Owner: -
--

COPY public.peptide_question_options (id, option_text, created_at, updated_at, deleted_at) FROM stdin;
1	1-3 months	2026-04-22 18:39:27.229156+00	2026-04-22 18:39:27.229156+00	\N
2	18-25	2026-04-22 18:39:27.229156+00	2026-04-22 18:39:27.229156+00	\N
3	2-3 times per week	2026-04-22 18:39:27.229156+00	2026-04-22 18:39:27.229156+00	\N
4	26-35	2026-04-22 18:39:27.229156+00	2026-04-22 18:39:27.229156+00	\N
5	3-6 months	2026-04-22 18:39:27.229156+00	2026-04-22 18:39:27.229156+00	\N
6	36-45	2026-04-22 18:39:27.229156+00	2026-04-22 18:39:27.229156+00	\N
7	46-55	2026-04-22 18:39:27.229156+00	2026-04-22 18:39:27.229156+00	\N
8	56-65	2026-04-22 18:39:27.229156+00	2026-04-22 18:39:27.229156+00	\N
9	6-12 months	2026-04-22 18:39:27.229156+00	2026-04-22 18:39:27.229156+00	\N
10	65+	2026-04-22 18:39:27.229156+00	2026-04-22 18:39:27.229156+00	\N
11	Anti-aging	2026-04-22 18:39:27.229156+00	2026-04-22 18:39:27.229156+00	\N
12	As needed	2026-04-22 18:39:27.229156+00	2026-04-22 18:39:27.229156+00	\N
13	Cognitive enhancement	2026-04-22 18:39:27.229156+00	2026-04-22 18:39:27.229156+00	\N
14	Currently using	2026-04-22 18:39:27.229156+00	2026-04-22 18:39:27.229156+00	\N
15	Definitely not	2026-04-22 18:39:27.229156+00	2026-04-22 18:39:27.229156+00	\N
16	Definitely yes	2026-04-22 18:39:27.229156+00	2026-04-22 18:39:27.229156+00	\N
17	Dizziness	2026-04-22 18:39:27.229156+00	2026-04-22 18:39:27.229156+00	\N
18	Every other day	2026-04-22 18:39:27.229156+00	2026-04-22 18:39:27.229156+00	\N
19	Fat loss	2026-04-22 18:39:27.229156+00	2026-04-22 18:39:27.229156+00	\N
20	Fatigue	2026-04-22 18:39:27.229156+00	2026-04-22 18:39:27.229156+00	\N
21	Female	2026-04-22 18:39:27.229156+00	2026-04-22 18:39:27.229156+00	\N
22	Friend/Family	2026-04-22 18:39:27.229156+00	2026-04-22 18:39:27.229156+00	\N
23	General wellness	2026-04-22 18:39:27.229156+00	2026-04-22 18:39:27.229156+00	\N
24	Headache	2026-04-22 18:39:27.229156+00	2026-04-22 18:39:27.229156+00	\N
25	Healthcare provider	2026-04-22 18:39:27.229156+00	2026-04-22 18:39:27.229156+00	\N
26	Injection site reaction	2026-04-22 18:39:27.229156+00	2026-04-22 18:39:27.229156+00	\N
27	Insomnia	2026-04-22 18:39:27.229156+00	2026-04-22 18:39:27.229156+00	\N
28	Joint pain	2026-04-22 18:39:27.229156+00	2026-04-22 18:39:27.229156+00	\N
29	Just researching	2026-04-22 18:39:27.229156+00	2026-04-22 18:39:27.229156+00	\N
30	Less than 1 month	2026-04-22 18:39:27.229156+00	2026-04-22 18:39:27.229156+00	\N
31	Male	2026-04-22 18:39:27.229156+00	2026-04-22 18:39:27.229156+00	\N
32	Muscle growth	2026-04-22 18:39:27.229156+00	2026-04-22 18:39:27.229156+00	\N
33	Nausea	2026-04-22 18:39:27.229156+00	2026-04-22 18:39:27.229156+00	\N
34	Neutral	2026-04-22 18:39:27.229156+00	2026-04-22 18:39:27.229156+00	\N
35	No side effects	2026-04-22 18:39:27.229156+00	2026-04-22 18:39:27.229156+00	\N
36	Non-binary	2026-04-22 18:39:27.229156+00	2026-04-22 18:39:27.229156+00	\N
37	Not applicable	2026-04-22 18:39:27.229156+00	2026-04-22 18:39:27.229156+00	\N
38	Not effective at all	2026-04-22 18:39:27.229156+00	2026-04-22 18:39:27.229156+00	\N
39	Not sure	2026-04-22 18:39:27.229156+00	2026-04-22 18:39:27.229156+00	\N
40	Not very effective	2026-04-22 18:39:27.229156+00	2026-04-22 18:39:27.229156+00	\N
41	Once daily	2026-04-22 18:39:27.229156+00	2026-04-22 18:39:27.229156+00	\N
42	Once per week	2026-04-22 18:39:27.229156+00	2026-04-22 18:39:27.229156+00	\N
43	Online research	2026-04-22 18:39:27.229156+00	2026-04-22 18:39:27.229156+00	\N
44	Other (please specify)	2026-04-22 18:39:27.229156+00	2026-04-22 18:39:27.229156+00	\N
45	Over 1 year	2026-04-22 18:39:27.229156+00	2026-04-22 18:39:27.229156+00	\N
46	Planning to start	2026-04-22 18:39:27.229156+00	2026-04-22 18:39:27.229156+00	\N
47	Prefer not to say	2026-04-22 18:39:27.229156+00	2026-04-22 18:39:27.229156+00	\N
48	Probably not	2026-04-22 18:39:27.229156+00	2026-04-22 18:39:27.229156+00	\N
49	Probably yes	2026-04-22 18:39:27.229156+00	2026-04-22 18:39:27.229156+00	\N
50	Recovery/Healing	2026-04-22 18:39:27.229156+00	2026-04-22 18:39:27.229156+00	\N
51	Reddit/Forums	2026-04-22 18:39:27.229156+00	2026-04-22 18:39:27.229156+00	\N
52	Social media	2026-04-22 18:39:27.229156+00	2026-04-22 18:39:27.229156+00	\N
53	Somewhat effective	2026-04-22 18:39:27.229156+00	2026-04-22 18:39:27.229156+00	\N
54	Too early to tell	2026-04-22 18:39:27.229156+00	2026-04-22 18:39:27.229156+00	\N
55	Twice daily	2026-04-22 18:39:27.229156+00	2026-04-22 18:39:27.229156+00	\N
56	Used in the past	2026-04-22 18:39:27.229156+00	2026-04-22 18:39:27.229156+00	\N
57	Very effective	2026-04-22 18:39:27.229156+00	2026-04-22 18:39:27.229156+00	\N
58	Water retention	2026-04-22 18:39:27.229156+00	2026-04-22 18:39:27.229156+00	\N
59	YouTube/Podcast	2026-04-22 18:39:27.229156+00	2026-04-22 18:39:27.229156+00	\N
\.


--
-- Data for Name: peptide_questions; Type: TABLE DATA; Schema: public; Owner: -
--

COPY public.peptide_questions (id, question_text, question_type, created_at, updated_at, deleted_at) FROM stdin;
1	What is your experience with this peptide?	single_choice	2026-04-22 18:39:27.229156+00	2026-04-22 18:39:27.229156+00	\N
2	How long have you been using (or did you use) it?	single_choice	2026-04-22 18:39:27.229156+00	2026-04-22 18:39:27.229156+00	\N
3	What is your age range?	single_choice	2026-04-22 18:39:27.229156+00	2026-04-22 18:39:27.229156+00	\N
4	What is your gender?	single_choice	2026-04-22 18:39:27.229156+00	2026-04-22 18:39:27.229156+00	\N
5	What is your primary goal with this peptide?	single_choice	2026-04-22 18:39:27.229156+00	2026-04-22 18:39:27.229156+00	\N
6	How effective has it been for your goals?	single_choice	2026-04-22 18:39:27.229156+00	2026-04-22 18:39:27.229156+00	\N
7	Have you experienced any side effects?	multiple_choice	2026-04-22 18:39:27.229156+00	2026-04-22 18:39:27.229156+00	\N
8	How often do you dose?	single_choice	2026-04-22 18:39:27.229156+00	2026-04-22 18:39:27.229156+00	\N
9	Would you recommend this peptide to others?	single_choice	2026-04-22 18:39:27.229156+00	2026-04-22 18:39:27.229156+00	\N
10	How did you first learn about this peptide?	single_choice	2026-04-22 18:39:27.229156+00	2026-04-22 18:39:27.229156+00	\N
\.


--
-- Data for Name: peptide_references; Type: TABLE DATA; Schema: public; Owner: -
--

COPY public.peptide_references (id, peptide_id, reference_type, study_id, citation_id, context, created_at, updated_at) FROM stdin;
\.


--
-- Data for Name: peptide_research_indication_studies; Type: TABLE DATA; Schema: public; Owner: -
--

COPY public.peptide_research_indication_studies (id, indication_id, protocol_id, study_title, study_description, created_at, updated_at) FROM stdin;
\.


--
-- Data for Name: peptide_research_indications; Type: TABLE DATA; Schema: public; Owner: -
--

COPY public.peptide_research_indications (id, peptide_id, indication_title, effectiveness_tag, created_at, updated_at, description) FROM stdin;
\.


--
-- Data for Name: peptide_side_effects; Type: TABLE DATA; Schema: public; Owner: -
--

COPY public.peptide_side_effects (id, peptide_id, side_effect_id, created_at, updated_at) FROM stdin;
\.


--
-- Data for Name: peptides; Type: TABLE DATA; Schema: public; Owner: -
--

COPY public.peptides (id, slug, category_id, sequence, synonyms, overview, mechanism_of_action, two_d_structure_photo, iupac_name, molecular_mass, molecular_formula, potential_research_fields, chemical_formula, name, fda_approval_status, wada_status, research_level, chain_length, peptide_type, modifications, storage_temperature, shelf_life_reconstituted, cycle_duration, break_period, effect_onset, required_materials, safety_guidelines, contraindications, stop_signs, quality_checks, key_information, is_popular, deleted_at, created_at, updated_at, half_life_value, half_life_unit) FROM stdin;
184	fladrafinil	25	\N	fluorafinil, bisfluoroadrafinil	Fladrafinil is a modafinil prodrug derivative of adrafinil - the most basic prodrug of modafinil and is closely related to flmodafinil.	It produces wakefulness akin to modafinil and other deriratives of it by interacting with adrenergic, histaminergic and dopaminergic systems. Additionally it produces anti-aggresive effects which adrafinil does not. It is 3-4 times more potent than adrafinil.	https://pubchem.ncbi.nlm.nih.gov/image/imgsrv.fcgi?cid=13316557&t=l	2-{[Bis(4-fluorophenyl)methyl]sulfinyl}-N-hydroxyacetamide	325.33 g/mol	\N	Narcolepsy, Executive Function	C15H13F2NO3S	Fladrafinil	\N	\N	\N	\N	\N	\N	\N	\N	\N	\N	\N	\N	\N	\N	\N	\N	\N	f	\N	2025-11-04 18:02:09+00	2025-11-04 18:50:18+00	\N	\N
120	cjc-1295-no-dac	4	Tyr-D-Ala-Asp-Ala-Ile-Phe-Thr-Gln-Ser-Tyr-Arg-Lys-Val-Leu-Gly-Gln-Leu-Ser-Ala-Arg-Lys-Leu-Leu-Gln-Asp-Ile-Met-Ser-Arg-Gln-Gln	Growth hormone releasing hormone analog, Modified GNRH	CJC-1295 is a synthetic analog of growth hormone-releasing hormone (GHRH) that has been modified to increase its half-life and stability.	CJC-1295 binds to and activates GHRH receptors on somatotroph cells in the anterior pituitary, stimulating the synthesis and release of growth hormone.	https://pubchem.ncbi.nlm.nih.gov/image/imgsrv.fcgi?cid=91971820&t=l	\N	3367.88 g/mol	\N	Growth Hormone Deficiency, Anti-Aging, Muscle Wasting, Lipodystrophy, Metabolic Disorders	C152H252N44O42	CJC-1295 NO DAC	\N	\N	\N	\N	\N	\N	\N	\N	\N	\N	\N	\N	\N	\N	\N	\N	\N	f	\N	2025-08-21 16:14:05+00	2025-09-29 07:40:14+00	\N	\N
195	itpp	19	\N	myo-Inositol trispyrophosphate	ITPP is a derirative of inositol researched for its performance enhancing effects.	ITPP works by allosterically regulating hemoglobin to allow oxygen to disassociate from hemoglobin into tissue easier. Research has demonstrated it increasing tissue oxygenation and increased endurance.	https://pubchem.ncbi.nlm.nih.gov/image/imgsrv.fcgi?cid=10439981&t=l	\N	605.984 g/mol	\N	Performance Enhancement, Dementia, Ischemia, Cancer	C6H12O21P6	ITPP	\N	\N	\N	\N	\N	\N	\N	\N	\N	\N	\N	\N	\N	\N	\N	\N	\N	f	\N	2025-11-07 03:27:24+00	2025-11-07 03:30:30+00	\N	\N
133	aicar	19	5-Aminoimidazole-4-carboxamide-1-β-D-ribofuranoside	Acadesine, AICA-riboside	AICAR, is an AMP-activated protein kinase activator which is used for the treatment of acute lymphoblastic leukemia and may have applications in treating other disorders such as diabetes. Acadesine has been used clinically to treat and protect against cardiac ischemic injury. The drug was first used in the 1980s as a method to preserve blood flow to the heart during surgery.	AICAR acts as an AMP-activated protein kinase agonist. It stimulates glucose uptake and increases the activity of p38 mitogen-activated protein kinases α and β in skeletal muscle tissue, as well as suppressing apoptosis by reducing production of reactive oxygen compounds inside the cell.	https://upload.wikimedia.org/wikipedia/commons/thumb/b/b0/Acadesine_structure.svg/250px-Acadesine_structure.svg.png	[(2R,3S,4R,5R)-5-(4-amino-1H-imidazo[4,5-c]pyridin-1-yl)-3,4-dihydroxyoxolan-2-yl]methyl dihydrogen phosphate	338.21 g/mol	\N	Metabolic Disease, Obesity, Cardiology, Cancer, Neurology	C9H15N4O8P	AICAR	\N	\N	\N	\N	\N	\N	\N	\N	\N	\N	\N	\N	\N	\N	\N	\N	\N	f	\N	2025-08-27 21:35:08+00	2025-09-08 00:57:46+00	\N	\N
153	nephrilin	3	Ac‑RGVTEDYLRLETLVQKVVSKGFYKKKQCRPSKGRKRGFCW‑amide	mTORC2 inhibitor peptide, PRR5-MBD fusion peptide	Nephrilin is a synthetic peptide specifically designed to inhibit mTORC2 short for mammalian target of rapamycin complex 2 by competing with its interaction with PRR5/Protor. It incorporates both a PRR5-derived segment and the metal-binding domain of IGFBP‑3 for targeted cellular uptake, particularly stressed cells, via iron-uptake pathways.	Nephrilin competes with PRR5 for binding to mTORC2, thereby reducing its activity. Given mTORC2’s role in activating AGC kinases, this interference can modulate stress and survival pathways. The MBD domain binds ferrous/ferric iron and facilitates peptide entry via transferrin receptor and integrin-β3, targeting stressed cells with altered iron metabolism. Nephrilin reverses ROS generation and oxidative stress markers such as p66shc phosphorylation, Ser36, NADPH oxidase activation, and inflammatory cytokine elevations. Lastly it modulates pathways connected to oxidative metabolism and stress responses involving Rac1, PKC-β, Prex1.	\N	\N	4.5–5 kDa	\N	Burn Trauma, Sepsis, Shock, Oxidative Stress, Epigenetic Remodeling, Anti-Aging, Metabolic Health, Regeneration	\N	Nephrilin	\N	\N	\N	\N	\N	\N	\N	\N	\N	\N	\N	\N	\N	\N	\N	\N	\N	f	\N	2025-09-03 02:50:45+00	2025-09-08 19:29:08+00	\N	\N
158	nad+	19	\N	\N	NAD⁺ is an essential coenzyme present in all living cells, acting as an electron carrier in redox reactions critical for energy metabolism, DNA repair, and signaling pathways involving sirtuins and PARPs. It oscillates between its oxidized form (NAD⁺) and reduced form (NADH) to enable these functions.	NAD⁺ accepts electrons during metabolic reactions, becoming NADH, which then donates electrons in processes such as oxidative phosphorylation and anabolic pathways. NAD+ serves as a substrate for enzymes like sirtuins, PARPs, and cADP-ribose synthases, facilitating DNA repair and protein modifications. In the hypothalamus, NAD⁺ modulates feeding behavior by entering neurons via connexin 43, activating SIRT1/FOXO1 pathways to suppress hunger-driving neuropeptides. In ischemic heart tissue, NAD⁺ reduces apoptotic signaling and improves antioxidant capacity.	https://upload.wikimedia.org/wikipedia/commons/thumb/f/fe/NAD%2B.svg/250px-NAD%2B.svg.png	[[(2R,3S,4R,5R)-5-(6-aminopurin-9-yl)-3,4-dihydroxyoxolan-2-yl]methoxy-oxidophosphoryl][(2R,3S,4R,5R)-5-(3-carbamoylpyridin-1-ium-1-yl)-3,4-dihydroxyoxolan-2-yl]methyl phosphate	663.4 g/mol	\N	Cardiovascular Health, Neurological Health, Mitochondrial Function, Obesity, Performance	C21H27N7O14P2	NAD+	\N	\N	\N	\N	\N	\N	\N	\N	\N	\N	\N	\N	\N	\N	\N	\N	\N	f	\N	2025-09-07 23:17:37+00	2025-09-27 16:46:41+00	\N	\N
237	bpc-157110	1	Gly-Glu-Pro-Pro-Pro-Gly-Lys-Pro-Ala-Asp-Asp-Ala-Gly-Leu-Val	Bepecin, PL 14736, PL-10	A synthetic peptide used to support tissue repair.	Activates fibroblast growth factor signaling.	https://example.com/structure.png	L-glycyl-L-alpha-glutamyl-L-prolyl-...	1419.5 g/mol	C62H98N16O22	Wound healing, regenerative medicine	C62H98N16O22	BPC-157110	not_approved	allowed	phase_2	15	linear	None	2-8°C	7 days	4-6 weeks	2 weeks	Quick	Bacteriostatic water	For research use only	Pregnancy	Severe pain	HPLC, MS	High purity	f	\N	2026-04-27 17:19:19.623711+00	2026-04-27 17:19:19.623717+00	4.5000	hours
162	thymogen	24	Glu–Trp	Glu–Trp dipeptide, sodium L-glutamyl-L-tryptophan	Thymogen is a synthetic dipeptide originally derived from thymus peptide extracts. It is considered a second-generation thymic immunomodulator, designed to reproduce the biological activity of natural thymic hormones in a defined, standardized form.	Thymogen penetrates lymphocyte nuclei and interacts with DNA regulatory regions. It upregulates transcription of genes related to T-cell receptor (TCR) synthesis and signal transduction pathways. It enhances mRNA stability for proteins involved in lymphocyte activation. Thymogen promotes differentiation of immature thymocytes into functional CD4+ and CD8+ T cells,\r\nstimulates IL-2 receptor expression - enhancing responsiveness to interleukin-2, normalizes helper-to-suppressor T-cell ratios. Thymogen enhances antigen presentation by increasing MHC class II molecule expression on macrophages and dendritic cells, activates natural killer cells and cytotoxic T lymphocytes, improving antiviral and antitumor defense, regulates cytokine production to restore balanced immune responses. Thymogen supports DNA repair and chromatin structure in immune cells, thereby prolonging their functional lifespan.	https://www.peptidesciences.com/media/wysiwyg/Thymagen_Molecule.png	(2S)-2-(3-(1H-indol-3-yl)-2-(methylamino)-3-oxopropanoylamino)pentanedioic acid	349.34 g/mol	\N	Genetic Modulation, Immunology, Immune System	C16H19N3O6	Thymogen	\N	\N	\N	\N	\N	\N	\N	\N	\N	\N	\N	\N	\N	\N	\N	\N	\N	f	\N	2025-09-11 16:52:41+00	2025-09-11 17:45:48+00	\N	\N
171	bacteriostatic-water	29	\N	Sterile water, Bacteriostatic water for injection, Water for injection, Sterile water for injection	Bacteriostatic water is a sterile, non-pyrogenic water preparation containing 0.9% (9 mg/mL) benzyl alcohol as a preservative / bacteriostatic agent. Because of the benzyl alcohol, it is supplied in a multiple-dose vial from which repeated withdrawals may be made, provided aseptic technique is used. The pH is typically ~5.7.	The benzyl alcohol does not kill all bacteria outright but inhibits their growth and reproduction, in other words: holds potential contaminants in a static state, hence the name bacteriostatic. This allows repeated puncture of the vial without overt overgrowth of microbial contaminants. In microbiology terms, this is distinguished from bactericidal agents.	\N	\N	108.14 g/mol	\N	Injectable reconstitution, Injectable Dilution, Intranasal Dilution, Preservation	\N	Bacteriostatic Water	\N	\N	\N	\N	\N	\N	\N	\N	\N	\N	\N	\N	\N	\N	\N	\N	\N	f	\N	2025-10-05 08:50:24+00	2025-10-05 09:24:31+00	\N	\N
172	acetic-acid	29	\N	Ethylic acid, Vinegar acid, Ethoic acid, Ethanoic acid	Acetic acid, better known as the acid part of vinegar, is a weak organic acid, medically used as a solvent and antiseptic.	Acetic acid partially dissociates into acetate when dissolved in water, resulting in a lower pH environment without complete dissociation. This reduced pH inhibits the growth and survival of many bacteria, fungi, and biofilms. Acidic conditions can also disrupt calcium or mineral encrustations. When acetic acid enters microbial cells in its undissociated form, it releases H⁺ ions, which further lowers the cytoplasmic pH, denatures proteins, disrupts enzyme functions, and damages cell membranes, ultimately weakening or killing the microorganisms. Additionally, acetic acid demonstrates effectiveness against biofilms, which are notoriously difficult to eliminate. Research indicates that at moderate concentrations, acetic acid can reduce biofilm formation, while higher concentrations or prolonged exposure can eliminate established biofilms. In the realm of pharmaceutical manufacturing, acetic acid aids in solubilizing weakly basic drugs, enhancing their solubility.	https://pubchem.ncbi.nlm.nih.gov/image/imgsrv.fcgi?cid=176&t=l	acetic acid	60.05 g/mol	\N	Wound care, Surgical Irrigation, Antiseptic, Urinary Tract Irrigation, Solvent, Dry Spray Production	C2H4O2	Acetic Acid	\N	\N	\N	\N	\N	\N	\N	\N	\N	\N	\N	\N	\N	\N	\N	\N	\N	f	\N	2025-10-05 09:24:24+00	2025-10-05 09:38:06+00	\N	\N
175	ptd-bdm	3	RRRRRRRRGGGGRKTGHQICKFRKC	EX-A13483, Protein Transduction Domain-fused Dishevelled Binding Motif	PTD-DBM is a peptide developed from the group up by a research team at Yonsei university in South Korea with the intention of reversing and preventing hairloss. It's effects are enhanced by Wnt/β-catenin signaling activators like Valproic acid.	PTD-DBM interferes with CXXC5 binding to Dishevelled which would otherwise cause negative feedback for Wnt/β-catenin pathway - a key regulator of cell proliferation and differentiation. This basically means that the Wnt/β-catenin mediated cell growth and proliferation is disinhibited by PTD-DPM. This is especially displayed in the hair as PTD-DBM can not only slow down hair loss but stimulate hair follicle development leading to regrowth. Wnt/β-catenin also stimulates insulin sensitivity in skeletal muscle cells. Lastly Wnt/β-catenin is incredibly relevant in neurology as it stimulaters neural stem cell proliferation, allowing for regeneration of nervous system cells.	https://pubchem.ncbi.nlm.nih.gov/image/imgsrv.fcgi?cid=176453931&t=l	H-Arg-Arg-Arg-Arg-Arg-Arg-Arg-Arg-Gly-Gly-Gly-Gly-Arg-Lys-Thr-Gly-His-Gln-Ile-Cys-Lys-Phe-Arg-Lys-Cys-OH	3082.6 g/mol	\N	Hair Loss, Insulin Sensitivity, Neurogenesis, Anemia, Vascular Development	C124H225N61O28S2	PTD-BDM	\N	\N	\N	\N	\N	\N	\N	\N	\N	\N	\N	\N	\N	\N	\N	\N	\N	f	\N	2025-10-07 10:50:41+00	2025-10-07 11:06:23+00	\N	\N
239	bpc-15711001	1	Gly-Glu-Pro-Pro-Pro-Gly-Lys-Pro-Ala-Asp-Asp-Ala-Gly-Leu-Val	Bepecin, PL 14736, PL-10	A synthetic peptide used to support tissue repair.	Activates fibroblast growth factor signaling.	https://example.com/structure.png	L-glycyl-L-alpha-glutamyl-L-prolyl-...	1419.5 g/mol	C62H98N16O22	Wound healing, regenerative medicine	C62H98N16O22	BPC-15711001	not_approved	allowed	phase_2	15	linear	None	2-8°C	7 days	4-6 weeks	2 weeks	Quick	Bacteriostatic water	For research use only	Pregnancy	Severe pain	HPLC, MS	High purity	f	\N	2026-04-27 17:40:30.173087+00	2026-04-27 17:40:30.173092+00	4.5000	hours
178	methylene-blue	19	\N	Methylthioninium chloride, Methylthionine Chloride, Swiss Blue, Basic Blue 9	Methylene blue (MB) is a synthetic heterocyclic aromatic chemical compound (a thiazine dye) first synthesized in 1876. It was one of the first synthetic drugs used in medicine and has diverse clinical and research applications.	MB is a redox-active compound that can alternate between oxidized and reduced forms. This allows MB to act as an artificial electron carrier, shuttling electrons in cellular systems. MB accepts electrons from NADPH via NADPH-methemoglobin reductase, reducing methemoglobin into functional hemoglobin. MB bypasses majority of the electron transfer chain, carrying electrons over from Complex I straight to Cytochrome C which gives it to Complex IV. This reduces ROS production and stimulates Complex IV activity, enhancing ATP production and lower oxidative stress. At higher doses it acts as a Acetylcholinesterase inhibitor and a Reversible Monoamine Oxidase A Inhibitor. It also inhibits NOS and sGC which is relevant for some individuals.	https://pubchem.ncbi.nlm.nih.gov/image/imgsrv.fcgi?cid=6099&t=l	[7-(dimethylamino)phenothiazin-3-ylidene]-dimethylazanium chloride	319.9 g/mol	\N	Neurodegenerative Diseases, AMPD1 Deficiency, Mitochondrial Disorders, Psychiatry, Cognitive Enhancement, Sepsis, Oxidative Stress, Anti-Aging	C16H18ClN3S	Methylene Blue	\N	\N	\N	\N	\N	\N	\N	\N	\N	\N	\N	\N	\N	\N	\N	\N	\N	f	\N	2025-10-13 16:05:54+00	2025-10-13 16:16:24+00	\N	\N
182	l-carnitine	19	\N	Levocarnitine	Carnitine is a compound involved in long chain fatty acid metabolism in the body. It is biosynthesized endogenously, however limitedly.	Carnitine forms long chain acylcarnitine esters with long chain fatty acids which are shuttled into the mitochondria using the carnitine shuttle, there they undergo beta-oxidation to produce ATP. It also acts as an acetyl donor for for coenzyme A, detoxifies acyl groups by forming acylcarnitine, regulates metabolism and acts as an anti-oxidant.	https://pubchem.ncbi.nlm.nih.gov/image/imgsrv.fcgi?cid=10917&t=l	3-hydroxy-4-(trimethylazaniumyl)butanoate	161.201 g/mol	\N	Fertility, Fat Loss, Vegan Diet, Performance	C7H15NO3	L-Carnitine	\N	\N	\N	\N	\N	\N	\N	\N	\N	\N	\N	\N	\N	\N	\N	\N	\N	f	\N	2025-11-04 01:29:12+00	2025-11-04 01:36:03+00	\N	\N
183	phenibut	25	\N	Anvifen, Aminophenylbutyric acid, β-Phenyl-GABA, Fenibut	Phenibut is a GABA derivative with a phenyl ring substitution. Phenyl ring allows phenibut's blood-brain barrier penetration, unlike GABA.	Phenibut acts as a selective full agonist of GABA-B receptor akin to baclofen and as an inhibitor of α2δ subunit Voltage Gated Calcium Channels akin to Pregabalin and Gabapentin. These mechanisms produce anxiety relief, pain relief and relaxation.	https://pubchem.ncbi.nlm.nih.gov/image/imgsrv.fcgi?cid=14113&t=l	4-Amino-3-phenylbutanoic acid	179.219 g/nol	\N	Anxiety, PTSD, Alcoholism, Neuropathy, Muscular Hypertonicity	C10H13NO2	Phenibut	\N	\N	\N	\N	\N	\N	\N	\N	\N	\N	\N	\N	\N	\N	\N	\N	\N	f	\N	2025-11-04 17:16:07+00	2025-11-04 17:24:06+00	\N	\N
185	oxiracetam	28	\N	ISF-2522	Oxiracetam is a synthetic nootropic compound belonging to the racetam family, a class of cognitive enhancers derived from piracetam. It is known to be more stimulating and potent than other racetams. It is also known as one of the most tolerable racetams.	Oxiracetam produces its effects through positive modulation of the AMPA receptor, while additionally increasing acetylcholine and glutamate neurotransmission. Oxiracetam has demonstrated enhancement of PKC activity and enhancement of phospholipid synthesis.	https://pubchem.ncbi.nlm.nih.gov/image/imgsrv.fcgi?cid=4626&t=l	(RS)-2-(4-hydroxy-2-oxopyrrolidin-1-yl)acetamide	158.157 g/mol	\N	Cognitive Enhancement, Neurodegeneration, Traumatic Brain Injury, Schizophrenia	C6H10N2O3	Oxiracetam	\N	\N	\N	\N	\N	\N	\N	\N	\N	\N	\N	\N	\N	\N	\N	\N	\N	f	\N	2025-11-04 22:38:28+00	2025-11-04 23:14:48+00	\N	\N
186	bromantane	25	\N	Bromantan, Ladasten, 87913-26-6	Bromantane—developed by Russia for neurasthenia, is a nootropic and an anxiolytic compound of the adamantane family. It's related to both amantadine and memantine.	Bromantane stimulates CREB, which disinhibits tyrosine hydroxylase- the rate-limiting step in dopamine synthesis. Bromantane additionally acts Kir2.1 inhibitor	https://pubchem.ncbi.nlm.nih.gov/image/imgsrv.fcgi?cid=4660557&t=l	N-(4-bromophenyl)adamantan-2-amine	306.24 g/mol	\N	Cognitive Enhancement, Depression, Anxiety, Parkinsons, ADHD, Neurodegeneration	C16H20BrN	Bromantane	\N	\N	\N	\N	\N	\N	\N	\N	\N	\N	\N	\N	\N	\N	\N	\N	\N	f	\N	2025-11-04 23:25:05+00	2025-11-29 13:11:31+00	\N	\N
187	noopept	25	\N	N-Phenylacetyl-l-prolylglycine ethyl ester, GVS-111, omberacetam	Noopept, also known as omberacetam, is a nootropic compound originally synthesized in Russia.  It is a prodrug  of cyclic glycine-proline while also having much more significant actions of its own. It is several orders of magnitudes more potent than piracetam.	Noopept acts as an agonist of AMPA and NMDA receptors and as an inhibitor of prolyl-hydroxylases which metabolize HIF-1a. The active metabolite CPG is an AMPA and GABA-A positive allosteric modulator. Glutamate pathway supports long term potentiation and synaptic plasticity, while HIF-1a stimulates regenerative actions such as erythropoietin and VEGF.	https://pubchem.ncbi.nlm.nih.gov/image/imgsrv.fcgi?cid=180496&t=l	Ethyl 1-(phenylacetyl)-l-prolylglycinate	318.373 g/mol	\N	Neurodegeneration, Cognitive Enhancement, Anxiety	C17H22N2O4	Noopept	\N	\N	\N	\N	\N	\N	\N	\N	\N	\N	\N	\N	\N	\N	\N	\N	\N	f	\N	2025-11-05 02:42:00+00	2025-11-05 05:44:04+00	\N	\N
188	meldonium	19	\N	THP, MET-8, Mildronate, Quaterine	Meldonium is a pharmaceutical developed in Latvia by Ivars Kalviņš as an anti-ischemia medication. It is prescribed for cardiovascular, neurological and metabolic diseases.	Meldonium inhibits carnitine biosynthesis and the carnitine shuttle which would otherwise produce acylcarnitine accumulation. It instead causes a metabolic shift of glycolysis and peroxisomal metabolism of long or branched fatty acids. Peroxisomes shortens these fatty acids into Medium-chain acyl-CoA's which do not require active transport and are subject to full oxidation. This pathway is less metabolically damaging and consumes less oxygen than otherwise. Additionally competitive inhibition of GBB metabolism frees GBB into an alternative route of esterification by an unknown enzyme, which produces GBB methyl ester and GBB ethyl ester, these GBB esters demonstrate cholinergic activity akin to acetylcholine.	https://pubchem.ncbi.nlm.nih.gov/image/imgsrv.fcgi?cid=123868&t=l	2-(2-Carboxylato-ethyl)-1,1,1-trimethylhydrazinium	146.190 g/mol	\N	Neurology, Diabetes, Atherosclerosis, Cardiovascular Disease, Metabolic Dysfunction	C6H14N2O2	Meldonium	\N	\N	\N	\N	\N	\N	\N	\N	\N	\N	\N	\N	\N	\N	\N	\N	\N	f	\N	2025-11-05 05:56:55+00	2025-11-05 19:01:06+00	\N	\N
189	gw-501516	19	\N	GW1516, GW-501, GSK-516, cardarine, endurobol	GW501516 is a compound developed for metabolic and cardiovascular diseases. It improves stamina, endurance, lipids, insulin sensitivity and more.	GW501516 is a selective PPAR-delta receptor agonist. PPAR-Delta activation causes increased Fatty acid oxidation and mitochondrial biogenesis. Additionally, it is anti-inflammatory and is protective against ischemia.	https://pubchem.ncbi.nlm.nih.gov/image/imgsrv.fcgi?cid=9803963&t=l	{2-methyl-4-[({4-methyl-2-[4-(trifluoromethyl)phenyl]-1,3-thiazol-5-yl}methyl)sulfanyl]-2-methylphenoxy}acetic acid	453.49 g/mol	\N	Performance Enhancement, Diabetes, Hyperlipidemia, Metabolic Disorders	C21H18F3NO3S2	GW-501516	\N	\N	\N	\N	\N	\N	\N	\N	\N	\N	\N	\N	\N	\N	\N	\N	\N	f	\N	2025-11-05 19:18:27+00	2025-11-05 21:51:07+00	\N	\N
190	9-me-bc	25	\N	9-Methyl-9H-β-carboline, 9-Methylnorharman, 9-MBC, N-Methyl-β-carboline, 9-Methyl-β-carboline	9-Me-BC is a heterocyclic amine of the beta-carboline family and is known for its nootropic effects. Its been proposed for investigation for Parkinsons.	9-Me-BC acts as an inhibitor of MAO-A as its main mechanism of action. Additionally it increases expression of tyrosine hydroxylase, reduces inflammatory cytokines, stimulates neurite outgrowth and the regeneration of neurons. It also stimulates expression of BDNF, NCAM1, TGFG-b2, Skp1, neurotrophin 3 and artemin.	https://pubchem.ncbi.nlm.nih.gov/image/imgsrv.fcgi?sid=350086076&deposited=t&version=1&t=l	5-Methyl-5H-pyrido[3,4-b]indole	182.226 g/mol	\N	Cognitive Enhancement, Neurodegeneration, Parkinson's Disease, Depression	C12H10N2	9-Me-BC	\N	\N	\N	\N	\N	\N	\N	\N	\N	\N	\N	\N	\N	\N	\N	\N	\N	f	\N	2025-11-05 22:09:08+00	2025-11-29 11:36:41+00	\N	\N
191	mk-677	28	\N	Ibutamoren, MK-0677, Oratrope	MK-677, now known as Ibutamoren is a potent oral growth hormone secretagogue and an appetite stimulant.	MK-677 acts as a potent GHS-R agonist. This mechanism is responsible for its effects of appetite stimulation, GH and IGF-1 secretion.	https://pubchem.ncbi.nlm.nih.gov/image/imgsrv.fcgi?cid=178024&t=l	2-amino-2-methyl-N-[1-(1-methylsulfonylspiro[2H-indole-3,4'-piperidine]-1'-yl)-1-oxo-3-phenylmethoxypropan-2-yl]propanamide	528.67 g/mol	\N	Sleep, Growth Hormone Deficiency, Performance Enhancement, Osteoporosis, Aging	C27H36N4O5S	MK-677	\N	\N	\N	\N	\N	\N	\N	\N	\N	\N	\N	\N	\N	\N	\N	\N	\N	f	\N	2025-11-06 01:03:13+00	2025-11-06 01:09:40+00	\N	\N
192	piracetam	25	\N	\N	Piracetam is a parent compound of the racetam family. it was originally used for epilepsy. It has shown efficacy in vertigo, dementia, dyslexia and more.	Piracetam works through a lot of pathways, notably modulating calcium channels, increasing NMDA and AMPA receptor binding, choline uptake enhancement, enhancing potassium stimulated release of:  D-aspartate, glutamane, acetylcholine, dopamine.	https://pubchem.ncbi.nlm.nih.gov/image/imgsrv.fcgi?cid=4843&t=l	2-(2-oxopyrrolidin-1-yl)acetamide	142.158 g/mol	\N	Neurodegeneration, Cognitive Decline, Vertigo, ADHD, Autism, Cognitive Enhancement	C6H10N2O2	Piracetam	\N	\N	\N	\N	\N	\N	\N	\N	\N	\N	\N	\N	\N	\N	\N	\N	\N	f	\N	2025-11-06 20:53:37+00	2025-11-06 21:05:40+00	\N	\N
193	phenylpiracetam	25	\N	fonturacetam, Phenotropil, Actitropil, Carphedon	Phenylpiracetam is a stimulant of the racetam family.  It is used for depresssion, cognitive decline, fatigue and ADHD.	Phenylpiracetam acts as a NDRI similiar to methylphenidate, additionally it acts as an agonist of a4b2 nicotinic acetylcholine receptors and a positive allosteric modulator of AMPA receptors.	https://pubchem.ncbi.nlm.nih.gov/image/imgsrv.fcgi?cid=132441&t=l	(R,S)-2-(2-oxo-4-phenylpyrrolidin-1-yl)acetamide	218.256 g/mol	\N	Cognitive Decline, Parkinson's Disease, ADHD, Cognitive Enhancement	C12H14N2O2	Phenylpiracetam	\N	\N	\N	\N	\N	\N	\N	\N	\N	\N	\N	\N	\N	\N	\N	\N	\N	f	\N	2025-11-06 21:42:59+00	2025-11-06 21:59:53+00	\N	\N
194	amino-tadalafil	1	\N	Tadalafil, Cialis	Amino Tadalafil is an analog of a well known erectile dysfunction medication Tadalafil (Cialis).	Amino tadalafil works much like standard tadalafil by inhibiting PDE-5 enzyme from breaking down cGMP. cGMP proceeds to promote vasodilation and promote browning of white adipose tissue. Compared to tadalafil, amino tadalafil supposedly has better stability in storage, better bioavailability and onset.	https://cdn2.caymanchem.com/cdn/productImages/20876.png	\N	390.4 g/mol	\N	Erectile Dysfunction, Hypertension, Metabolic Disorders, Fat Loss	C21H18N4O4	Amino Tadalafil	\N	\N	\N	\N	\N	\N	\N	\N	\N	\N	\N	\N	\N	\N	\N	\N	\N	f	\N	2025-11-07 03:16:31+00	2025-11-29 11:45:13+00	\N	\N
196	dada	19	\N	Diisopropylamine dichloroacetate, Liverall, Oxypangam, DIPA	Diisopropylamine dichloroacetate is the diisopropylamine salt of dichloroacetic acid. In Japan it is marketed under the trade name Liverall for the treatment of chronic liver conditions, including fatty liver and hepatitis.	Diisopropylamine dichloroacetate works by inhibiting Pyruvate dehydrogenase lipoamide kinase isozyme 4, which otherwise would proceed to inhibit PDC leading to inhibition of glycolysis. Because of this DADA is in effect a glycolysis disinhibitor. This effect attenuates hepatic steatosis by improving metabolic activity of the liver. Additionally it has shown anti-cancer effects.	https://pubchem.ncbi.nlm.nih.gov/image/imgsrv.fcgi?cid=12617&t=l	2,2-dichloroacetic acid;N-propan-2-ylpropan-2-amine	230.13 g/mol	\N	Cancer, Metabolic Disorders, Fatty liver, Hepatitis	C8H17Cl2NO2	DADA	\N	\N	\N	\N	\N	\N	\N	\N	\N	\N	\N	\N	\N	\N	\N	\N	\N	f	\N	2025-11-15 01:41:12+00	2025-11-15 01:50:29+00	\N	\N
197	sm-04554	3	\N	Dalosirvat, SM04554	SM-04554 is a compound that was under development for alopecia. It was cancelled after completing phase 3 trial.	SM-04554 specific mechanism has not been disclosed, however it acts as an activator of the Wnt/beta-catenin pathway. In hair follicle biology, Wnt signalling is critical for maintaining and initiating the anagen phase of hair follicles. Reduced Wnt signalling is associated with follicle miniaturisation and hair loss. In preclinical studies it increased total and nuclear β‑catenin in hair follicles, up‑regulated markers of proliferation, and increased expression of versican in follicular dermal papilla cells.	https://pubchem.ncbi.nlm.nih.gov/image/imgsrv.fcgi?cid=56837361&t=l	1-(2,3-dihydro-1,4-benzodioxin-6-yl)-4-phenylbutane-1,4-dione	296.322 g/mol	\N	Hair Loss	C18H16O4	SM-04554	\N	\N	\N	\N	\N	\N	\N	\N	\N	\N	\N	\N	\N	\N	\N	\N	\N	f	\N	2025-11-15 02:18:36+00	2025-11-15 02:25:25+00	\N	\N
198	dapoxetine	21	\N	Priligy	Dapoxetine is a selective serotonin reuptake inhibitor, initially developed as an antidepressant, but due to its short half life repurposed as a medication for premature ejaculation. It has recently been reconsidered as an aid for stress reduction.	By acutely inhibiting serotonin reuptake it causes a build up of serotonin. In regards to premature ejaculation dapoxetine inhibits ejaculatory expulsion reflex at supraspinal level by modulating activity of lateral paragigantocellular nucleus neurons. This causes an increase in pudendal motoneuron reflex discharge latency.	https://pubchem.ncbi.nlm.nih.gov/image/imgsrv.fcgi?cid=71353&t=l	(S)-N,N-Dimethyl-3-(naphthalen-1-yloxy)-1-phenylpropan-1-amine	305.421 g/mol	\N	Premature Ejaculation, Cognitive Enhancement, Anxiety, Depression, Stress Management	C21H23NO	Dapoxetine	\N	\N	\N	\N	\N	\N	\N	\N	\N	\N	\N	\N	\N	\N	\N	\N	\N	f	\N	2025-11-16 02:13:53+00	2025-11-29 15:01:51+00	\N	\N
199	phenibut-faa	25	\N	\N	Phenibut FAA is a GABA derivative with a phenyl ring substitution. Phenyl ring allows phenibut's blood-brain barrier penetration, unlike GABA. Unlike standard version, FAA also known as free amino acid form is is close to neutral pH, non-crystalline and has about 20% more phenibut molecules gram for gram. FAA form has the advantage of being more suitable for sublingual, rectal and intranasal use, however oral administration will form Phenibut HCL in the stomach.	Phenibut acts as a selective full agonist of GABA-B receptor akin to baclofen and as an inhibitor of α2δ subunit Voltage Gated Calcium Channels akin to Pregabalin and Gabapentin. These mechanisms produce anxiety relief, pain relief and relaxation.	https://pubchem.ncbi.nlm.nih.gov/image/imgsrv.fcgi?cid=14113&t=l	4-Amino-3-phenylbutanoic acid	179.219 g/nol	\N	Anxiety, PTSD, Alcoholism, Neuropathy, Muscular Hypertonicity	C10H13NO2	Phenibut FAA	\N	\N	\N	\N	\N	\N	\N	\N	\N	\N	\N	\N	\N	\N	\N	\N	\N	f	\N	2025-11-16 02:40:52+00	2025-11-16 02:46:23+00	\N	\N
201	cb-03-01	4	\N	Breezula, Clascoterone	CB-03-01, also know by its research name CB-03-01, is an antiandrogen useful for the treatment of acne and hair loss.	Clasterone is a steroidal antiandrogen with a potency comparable to cyproterone acetate. It has minimal systemic absorption, strong localized antiandrogenic activity and negligible systemic antiandrogenic activity even when administered subcutaneously. It is rapidly hydrolysed to cortexolone in systemic circulation.	https://pubchem.ncbi.nlm.nih.gov/image/imgsrv.fcgi?cid=11750009&t=l	[(8R,9S,10R,13S,14S,17R)-17-(2-hydroxyacetyl)-10,13-dimethyl-3-oxo-2,6,7,8,9,11,12,14,15,16-decahydro-1H-cyclopenta[a]phenanthren-17-yl] propanoate	402.5 g/mol	\N	Acne, Seborrheic Dermatitis, Hair Loss	C24H34O5	CB-03-01	\N	\N	\N	\N	\N	\N	\N	\N	\N	\N	\N	\N	\N	\N	\N	\N	\N	f	\N	2025-12-13 16:31:01+00	2025-12-13 16:37:27+00	\N	\N
202	ru-58841	4	\N	PSK-3841, HMR-3841	RU-58841 is a nonsteroidal antiandrogen developed in France for acne and hair loss.	RU-58841 itself has very low affinity for the androgen receptor, however once absorbed into tissue its broken down into more potent metabolites like RU-56279 and RU-59416.	https://pubchem.ncbi.nlm.nih.gov/image/imgsrv.fcgi?cid=132981&t=l	4-[3-(4-Hydroxybutyl)-4,4-dimethyl-2,5-dioxo-1-imidazolidinyl]-2-(trifluoromethyl)benzonitrile	369.344 g/mol	\N	Acne, Hair Loss, Seborrheic Dermatitis	C17H18F3N3O3	RU-58841	\N	\N	\N	\N	\N	\N	\N	\N	\N	\N	\N	\N	\N	\N	\N	\N	\N	f	\N	2025-12-13 17:10:49+00	2025-12-13 17:13:49+00	\N	\N
203	topilutamide	4	\N	Eucapil, Fluridil, BP-766	Topilutamide is a nonsteroidal antiandrogen developed for hair loss.	Topilutamide lacks systemic effects of significance while having local androgen receptor binding 9-15 times higher than more common antiandrogens.	https://pubchem.ncbi.nlm.nih.gov/image/imgsrv.fcgi?cid=44147451&t=l	2-hydroxy-2-methyl-N-[4-nitro-3-(trifluoromethyl)phenyl]-3-[(2,2,2-trifluoroacetyl)amino]propanamide	403.237 g/mol	\N	Acne, Seborrheic Dermatitis, Hair Loss	C13H11F6N3O5	Topilutamide	\N	\N	\N	\N	\N	\N	\N	\N	\N	\N	\N	\N	\N	\N	\N	\N	\N	f	\N	2025-12-13 17:31:34+00	2025-12-13 17:40:27+00	\N	\N
204	enclomiphene	4	\N	Androxal, EnCyzix, Clomifene, Enclomid, Enclomiphene citrate	Enclomiphene is a nonsteroidal selective estrogen receptor modulator, most famous for being a testosterone booster.	Enclomiphene antagonizes estrogen receptors systemically, but most notably in the pituitary, leading to reduced negative feedback on the HPG axis, therefore acting as a testosterone booster. It is the E stereoisomer of clomifene which additionally has the Z stereoisomer zuclomiphene, which is more estrogenic in contrast to enclomiphene and therefore antigonadotropic.	https://pubchem.ncbi.nlm.nih.gov/image/imgsrv.fcgi?cid=1548953&t=l	2-[4-[(E)-2-chloro-1,2-diphenylethenyl]phenoxy]-N,N-diethylethanamine	405.97 g/mol	\N	Hypogonadism, Cessation of Exogenous Hormones, Fertility	C26H28ClNO	Enclomiphene	\N	\N	\N	\N	\N	\N	\N	\N	\N	\N	\N	\N	\N	\N	\N	\N	\N	f	\N	2025-12-14 17:35:40+00	2025-12-14 17:45:00+00	\N	\N
211	canaglifozin	20	\N	Invokana, Sulisent, Prominad	Canagliflozin is a medication used to treat heart failure, kidney failure and type 2 diabetes.	Canaglifozin is an inhibitor of SGLT2 which is responsible for renal glucose reabsorption. Its inhibition causes increased carbohydrate and water excretion responsible for blood glucose reduction and blood pressure reduction. Cardiovascular and Kidney protective effects are partially or entirely independant from the glucose excretion as its mediated by reduced albuminuria, increased antiinflammatory and antifibrotic pathways, improved renal oxygenation.	\N	(2S,3R,4R,5S,6R)-2-(3-{[5-(4-fluorophenyl)thiophen-2-yl]methyl}-4-methylphenyl)-6-(hydroxymethyl)oxane-3,4,5-triol	444.52 g/mol	\N	CKD, CVD, Type 2 Diabetes, Anti-Aging	C24H25FO5S	Canaglifozin	\N	\N	\N	\N	\N	\N	\N	\N	\N	\N	\N	\N	\N	\N	\N	\N	\N	f	\N	2025-12-18 23:18:49+00	2025-12-18 23:26:25+00	\N	\N
212	empagliflozin	20	\N	Jardiance, BI-10773	Empagliflozin is a medication used to treat heart failure, kidney failure and type 2 diabetes. In contrast to Canaglifozin it has a more favorable side effect profile due to lower risk of UTI and one of the highest selectivity for SGLT-2	Empaglifozin is one of the most selective inhibitor of SGLT2 which is responsible for renal glucose reabsorption. Its inhibition causes increased carbohydrate and water excretion responsible for blood glucose reduction and blood pressure reduction. Cardiovascular and Kidney protective effects are partially or entirely independant from the glucose excretion as its mediated by reduced albuminuria, increased anti-inflammatory and antifibrotic pathways, improved renal oxygenation.	\N	(2S,3R,4R,5S,6R)-2-(4-chloro-3-{[4-((3S)-oxolan-3-yl)oxyphenyl]methyl}phenyl)-6-(hydroxymethyl)oxane-3,4,5-triol	450.91 g/mol	\N	CKD, CVD, Type 2 Diabetes, Anti-Aging	C23H27ClO7	Empagliflozin	\N	\N	\N	\N	\N	\N	\N	\N	\N	\N	\N	\N	\N	\N	\N	\N	\N	f	\N	2025-12-19 00:09:05+00	2025-12-19 00:17:45+00	\N	\N
214	idubilast	5	\N	Ketas, Pinatos, Eyevinal, AV-411, MN-166	Ibudilast  is an anti-inflammatory drug used in Japan. Its mainly prescribed for asthma.	Idubilast is a PDE inhibitor with highest potency at PDE4 and secondary affinity for PDE3, PDE10A, PDE11. In addition to that it is a potent inhibitor of TLR4 receptor which is responsible for a large portion of metabolic, inflammatory and algesic effects of saturated fats, opioids, alcohol and LPS.	https://pubchem.ncbi.nlm.nih.gov/image/imgsrv.fcgi?cid=3671&t=l	2-Methyl-1-(2-propan-2-ylpyrazolo[1,5-a]pyridin-3-yl)propan-1-one	230.311 g/mol	\N	Addiction, Chronic Pain, Metabolic Disorder, Depression, Inflammation, Asthma, Neuropathic Pain	C14H18N2O	Idubilast	\N	\N	\N	\N	\N	\N	\N	\N	\N	\N	\N	\N	\N	\N	\N	\N	\N	f	\N	2025-12-19 23:28:58+00	2025-12-19 23:36:18+00	\N	\N
209	testagen	24	H-KEDG-OH	KEDG	Testagen is part of the Khavinson peptides and is a short signaling peptide. Related to male reproductive health, testagen may influence testosterone levels and improve reproductive function.	Testagen enhance Leydig cell metabolic activity, improve mitochondrial efficiency within these cells, and supports steroidogenesis. It is believed to act through epigenetic modulation,	\N	\N	376.41 g/molaaaaaaaaaaa	\N	Fertility, Hypogonadism, Hormonal Balance	C17H29N5O9	Testagen	\N	\N	\N	\N	\N	\N	\N	\N	\N	\N	\N	\N	\N	\N	\N	\N	\N	f	\N	2025-12-16 21:29:50+00	2026-04-23 01:39:39.818334+00	\N	\N
215	riociguat	13	\N	Adempas, BAY 63-2521	Riociguat is a medication primarily used for pulmanory hypertension.	Riociguat is a stimulator of soluble guanylyl cyclase, same mechanism as Nitric Oxide-mediated vasodilation. sGC produces cGMP which causes smooth muscle relaxation.	https://pubchem.ncbi.nlm.nih.gov/image/imgsrv.fcgi?cid=11304743&t=l	Methyl N-[4,6-Diamino-2-[1-[(2-fluorophenyl)methyl]-1H-pyrazolo[3,4-b]pyridin-3-yl]-5-pyrimidinyl]-N-methyl-carbaminate	422.424 g/mol	\N	Erectile Dysfunction, Endothelial Dysfunction	C20H19FN8O2	Riociguat	\N	\N	\N	\N	\N	\N	\N	\N	\N	\N	\N	\N	\N	\N	\N	\N	\N	f	\N	2025-12-20 01:57:01+00	2025-12-21 00:54:47+00	\N	\N
217	fasudil	20	\N	AT-877, HA-1077	Fasudil is a Rho-kinase inhibitor and vasodilator used in China and Japan.	Fasudil works by inhibiting ROCK which downstream downregulates ACE and Ang-II, upregulates eNOS, downregulates ERK. Additionally it directly modulates Alpha-synuclein aggregation.	https://pubchem.ncbi.nlm.nih.gov/image/imgsrv.fcgi?cid=3547&t=l	5-(1,4-diazepan-1-ylsulfonyl)isoquinoline	291.37 g/mol	\N	Cognitive Decline, Hypertension, Erectile Dysfunction, Heart Failure	C14H17N3O2S	Fasudil	\N	\N	\N	\N	\N	\N	\N	\N	\N	\N	\N	\N	\N	\N	\N	\N	\N	f	\N	2026-01-16 23:21:32+00	2026-01-16 23:28:16+00	\N	\N
2	tb-500	3	Ac-Leu-Lys-Lys-Thr-Glu-Thr-Gln-OH	Thymosin Beta-4, TB4	TB-500 is a synthetic version of Thymosin Beta-4, a naturally occurring peptide that plays a crucial role in wound healing, tissue repair, and cellular regeneration. It is produced by the thymus gland and found in high concentrations in platelets, macrophages, and other cells involved in tissue repair.	TB-500 works by binding to actin, a protein that forms the structural framework of cells. This binding promotes cell migration, angiogenesis (formation of new blood vessels), and tissue regeneration. It also has anti-inflammatory properties and can reduce scar tissue formation.	https://imagedelivery.net/ey2i3L8oxd4cGMILqBg6mg/4006ad4a-280e-4b13-f4c5-de5775c4e000/public	N-acetyl-L-leucyl-L-lysyl-L-lysyl-L-threonyl-L-glutamyl-L-threonyl-L-glutaminamide	889.01 g/mol	\N	Wound healing, tissue repair, cardiovascular health, muscle recovery, anti-aging, neuroprotection	C38H68N10O14	TB-500	\N	\N	\N	\N	\N	\N	\N	\N	\N	\N	\N	\N	\N	\N	\N	\N	\N	f	\N	2025-04-15 02:28:26+00	2026-04-23 01:39:39.818334+00	2.5000	hours
3	mt-2	4	Ac-Nle-Asp-His-D-Phe-Arg-Trp-Lys-NH2 (cyclic)	Melanotan II, MTII, MT-II	Melanotan II is a synthetic peptide hormone that stimulates melanogenesis (tanning) and has effects on sexual arousal and appetite suppression. It is an analog of the naturally occurring hormone alpha-melanocyte stimulating hormone (alpha-MSH).	MT-2 acts as a non-selective agonist of melanocortin receptors (MC1R, MC3R, MC4R, MC5R). Activation of MC1R stimulates melanogenesis, MC4R affects sexual arousal and appetite, while MC3R and MC5R have various metabolic effects.	https://imagedelivery.net/ey2i3L8oxd4cGMILqBg6mg/c5b1813d-013b-4abc-d06d-a68a571e8900/public	cyclo[Nle4,Asp5,D-Phe7,Lys10]alpha-MSH(4-10)amide	1024.18 g/mol	\N	Dermatology, sexual dysfunction, appetite regulation, metabolic disorders	C50H69N15O9	MT-2	\N	\N	\N	\N	\N	\N	\N	\N	\N	\N	\N	\N	\N	\N	\N	\N	\N	f	\N	2025-04-15 02:28:26+00	2026-04-23 01:39:39.818334+00	0.7500	hours
180	mt-1	19	SYSXEHFRWGKPV	Afamelanotide, 4-Norleucyl-7-phenylalanine-alpha-msh, Melanotan, Scenesse	Melanotan is a peptide medically used for tanning. It is weaker relative to MT-2 but much more selective to MC1 which is responsible for tanning effects.	Melanotan produces tanning by selectively activating MC1 receptor. It was developed to be superior in selectivity and potency to alpha-MSH.	https://pubchem.ncbi.nlm.nih.gov/image/imgsrv.fcgi?cid=16197727&t=l	N-acetyl-L-seryl-L-tyrosyl-L-seryl-L-norleucyl-L-alpha-glutamyl-L-histidyl-D-phenylalanyl-L-arginyl-L-tryptophyl-glycyl-L-lysyl-L-prolyl-L-valinamide	1646.8 g/mol	\N	Tanning, Skin cancer	C78H111N21O19	MT-1	\N	\N	\N	\N	\N	\N	\N	\N	\N	\N	\N	\N	\N	\N	\N	\N	\N	f	\N	2025-11-03 23:41:20+00	2026-04-23 01:39:39.818334+00	0.5000	hours
4	kpv	5	Lys-Pro-Val	Tripeptide KPV, Lysine-Proline-Valine	KPV is a tripeptide derived from alpha-melanocyte stimulating hormone (alpha-MSH) that exhibits potent anti-inflammatory properties. Unlike its parent hormone, KPV does not cause skin pigmentation but retains the anti-inflammatory effects.	KPV exerts its anti-inflammatory effects by inhibiting NF-kB activation and reducing the production of pro-inflammatory cytokines such as TNF-alpha, IL-1beta, and IL-6. It also modulates immune cell function and promotes tissue repair.	https://imagedelivery.net/ey2i3L8oxd4cGMILqBg6mg/69750036-dea2-4318-edc3-e71fd3710d00/public	L-lysyl-L-prolyl-L-valine	371.46 g/mol	\N	Inflammatory bowel disease, dermatitis, wound healing, autoimmune disorders	C16H31N5O4	KPV	\N	\N	\N	\N	\N	\N	\N	\N	\N	\N	\N	\N	\N	\N	\N	\N	\N	f	\N	2025-04-15 02:28:26+00	2026-04-23 01:39:39.818334+00	2.5000	hours
18	oxytocin	13	Cys-Tyr-Ile-Gln-Asn-Cys-Pro-Leu-Gly-NH2 (with disulfide bond)	OT, Love hormone, Pitocin, Syntocinon	Oxytocin is a naturally occurring neuropeptide hormone produced in the hypothalamus and released by the posterior pituitary gland. It plays crucial roles in social bonding, trust, empathy, and relationship-building, earning it the nickname love hormone.	Oxytocin binds to oxytocin receptors (OXTR) in the brain and peripheral tissues. In the brain, it modulates social behavior, stress response, and emotional regulation, appetite. Peripherally, it affects smooth muscle contraction, senescence and various physiological processes.	https://pubchem.ncbi.nlm.nih.gov/image/imgsrv.fcgi?cid=439302&t=l	L-cysteinyl-L-tyrosyl-L-isoleucyl-L-glutaminyl-L-asparaginyl-L-cysteinyl-L-prolyl-L-leucylglycinamide cyclic (1-6)-disulfide	1007.19 g/mol	\N	Social Behavior, Autism Spectrum Disorders, Anxiety, Depression, PTSD, Relationship Therapy, Obesity, Muscle Wasting	C43H66N12O12S2	Oxytocin	\N	\N	\N	\N	\N	\N	\N	\N	\N	\N	\N	\N	\N	\N	\N	\N	\N	f	\N	2025-04-15 02:28:26+00	2026-04-23 01:39:39.818334+00	5.0000	minutes
19	hcg	4	Complex glycoprotein with alpha and beta subunits	Human Chorionic Gonadotropin, beta-hCG, Pregnyl	Human Chorionic Gonadotropin (hCG) is a glycoprotein hormone produced during pregnancy. In therapeutic applications, it is used to stimulate testosterone production in males and support fertility treatments in both sexes.	hCG mimics luteinizing hormone (LH) by binding to LH/CG receptors. In males, it stimulates Leydig cells to produce testosterone and supports spermatogenesis. In females, it can trigger ovulation and support corpus luteum function.	https://imagedelivery.net/ey2i3L8oxd4cGMILqBg6mg/1f7feb81-23fc-4469-ee9f-c76de27d2300/public	Human chorionic gonadotropin	36700 Da	\N	Male hypogonadism, fertility treatment, weight management, testosterone replacement therapy	Complex glycoprotein	HCG	\N	\N	\N	\N	\N	\N	\N	\N	\N	\N	\N	\N	\N	\N	\N	\N	\N	f	\N	2025-04-15 02:28:26+00	2026-04-23 01:39:39.818334+00	30.0000	hours
131	hmg	4	\N	FSH/LH, Menotropin, human menopausal gonadotropin, Fertinex, Gynogen HP, Humog, Humegon, Menopur, Merional, Meriofert, Menogon, Metrodin, Reprone, Pergonal, HMG Massone	HMG is a urine-derived gonadotropin mixture containing both FSH and LH. It is widely used in treatments for infertility - stimulating ovarian follicle development in women and spermatogenesis in men.	FSH: Binds to receptors on ovarian follicles or Sertoli cells, stimulating follicular growth or sperm maturation.\r\nLH: Acts on ovarian theca cells to trigger ovulation, and on Leydig cells to promote testosterone synthesis, supporting further gamete development.	\N	\N	\N	\N	Infertility, Hypogonadism	\N	HMG	\N	\N	\N	\N	\N	\N	\N	\N	\N	\N	\N	\N	\N	\N	\N	\N	\N	f	\N	2025-08-27 20:41:04+00	2026-04-23 01:39:39.818334+00	53.0000	hours
21	semax	21	Met-Glu-His-Phe-Pro-Gly-Pro	MEHFPGP, Semax peptide	Semax is a heptapeptide and synthetic fragment of adrenocorticotropic hormone (ACTH) that has been studied for its potential in cognition, neurogenesis, and neuroprotection. It is currently not FDA approved, though it has quite a few human trials. Semax has been studied for uses in stroke treatment, with trials using post-stroke human patients as well as pMCAO induced rodents. It has also been discussed in applications of ADHD in hypothetical mechanistic articles.\r\n\r\nIt is bioavailable in injectable form (subcutaneous, intramuscular, i.p.) and intranasally, but it is not bioavailable orally due to degradation by peptidases in the stomach/intestinal tract.	Semax has a variety of elucidated and hypothesized mechanisms. Its main mechanism seems to be its ability to increase brain-derived neurotrophic factor (BDNF), thus potentiating downstream neuroprotective and neurotropic action. \r\n\r\nSemax also increases the expression of several genes related to the immune and vascular systems. Particularly, those associated with are associated with processes like the development and migration of endothelial tissue, the migration of smooth muscle cells, hematopoiesis, and vasculogenesis.	https://imagedelivery.net/ey2i3L8oxd4cGMILqBg6mg/c7087a8d-dc07-468d-9ebd-120d403bdd00/public	(2S)-1-[2-[[(2S)-1-[(2S)-2-[[(2S)-2-[[(2S)-2-[[(2S)-2-amino-4-methylsulfanylbutanoyl]amino]-4-carboxybutanoyl]amino]-3-(1H-imidazol-5-yl)propanoyl]amino]-3-phenylpropanoyl]pyrrolidine-2-carbonyl]amino]acetyl]pyrrolidine-2-carboxylic acid	813.92 g/mol	\N	Cognitive enhancement, neuroprotection, stroke recovery, ADHD, memory improvement, anxiety	C37H51N9O10S	Semax	\N	\N	\N	\N	\N	\N	\N	\N	\N	\N	\N	\N	\N	\N	\N	\N	\N	f	\N	2025-04-15 02:28:26+00	2026-04-23 01:39:39.818334+00	7.0000	minutes
22	pt-141	21	Ac-Nle-cyclo[Asp-His-D-Phe-Arg-Trp-Lys]-OH	Bremelanotide, BMT, Vyleesi	Bremelanotide, more commonly known as PT-141, is a cyclic heptapeptide used to promote sexual drive. It is a synthetic derivative of alpha-melanocyte stimulating hormone and an active metabolite of MT-2. It is currently FDA approved for the treatment of female hypoactive sexual desire disorder (HSSD) in the brand name Vyleesi. \r\n\r\nBremelanotide is slightly pharmacologically different from MT-2, though it still possesses similar side-effects to MT-2, including nausea, flushing, and headache.	Bremelanotide works by selectively agonizing the melanocortin receptors - specifically, the melanocortin 3 and 4 receptors. These receptors are located in certain brain regions associated with sexual function. Agonism of these receptors may also downstream cause increases in dopamine, further explaining their mechanism of increasing sexual drive. It does have a weaker affinity for the MC1 and MC5 receptors, but the affinity is not considered high enough for the drug to be considered a target for these receptors.	https://imagedelivery.net/ey2i3L8oxd4cGMILqBg6mg/3c93ed55-4669-4a31-513e-5b2e7e904400/public	(3S,6S,9R,12S,15S,23S)-15-[(N-Acetyl-L-norleucyl)amino]-9-benzyl-6-{3-[(diaminomethylidene)amino]propyl}-12-(1H-imidazol-5-ylmethyl)-3-(1H-indol-3-ylmethyl)-2,5,8,11,14,17-hexaoxo-1,4,7,10,13,18-hexaazacyclotricosane-23-carboxylic acid	1025.182 g/mol	\N	Female sexual dysfunction, erectile dysfunction, libido enhancement, sexual arousal disorders	C50H68N14O10	PT-141	\N	\N	\N	\N	\N	\N	\N	\N	\N	\N	\N	\N	\N	\N	\N	\N	\N	f	\N	2025-04-15 02:28:26+00	2026-04-23 01:39:39.818334+00	2.7500	hours
23	retatrutide	19	YAÂ¹QGTFTSDYSILÂ²LDKKâ´AQAÂ¹AFIEYLLEGGPSSGAPPPSÂ³	LY3437943, Triple agonist peptide	Retatrutide is an investigational once-weekly injectable drug developed by Eli Lilly that targets the GLP-1, GIP, and glucagon receptors. It is designed to reduce appetite, improve insulin sensitivity, and increase energy expenditure. Early clinical trials show exceptionally strong weight-loss results, with some participants losing over 20% of their body weight. In comparison to other GLP-1 agonists, it presents a much more tolerable profile.	Retatrutide promotes weight loss by agonizing three glucagon-related receptors: the glucagon-like peptide 1 (GLP-1) receptor, the gastric inhibitory peptide (GIP) receptor, and the G-coupled glucagon receptor (GCCR). By agonizing these receptors, retatrutide effectively modulates glycemic-related functions.\r\n\r\nThe agonism of the GLP-1 receptor in the paraventricular nucleus in the brain results in appetite suppression, and agonism of this receptor in the body slows gastric emptying and promotes insulin release by the pancreatic beta cells. Agonism of the GIP receptors in the pancreas also promotes insulin secretion in a glucose-dependant manner. Finally, agonism of the GCCR promotes direct lipolysis and increases BMR, as well as mobilization of triglycerides.	https://imagedelivery.net/ey2i3L8oxd4cGMILqBg6mg/48cd2bf2-7bda-4984-74bf-a05f52a84e00/public	\N	4845.444 g/mol	\N	Obesity, type 2 diabetes, weight management, metabolic syndrome	C223H343F3N46O70	Retatrutide	\N	\N	\N	\N	\N	\N	\N	\N	\N	\N	\N	\N	\N	\N	\N	\N	\N	f	\N	2025-04-15 02:28:26+00	2026-04-23 01:39:39.818334+00	6.5000	days
24	selank	21	Thr-Lys-Pro-Arg-Pro-Gly-Pro	TKPRPGP, Selank peptide	Selank is an anxiolytic heptapeptide used for its cognitive enhancing and anxiolytic properties. It is a synthetic analogue of the endogenous immunomodulatory peptide tuftsin. In rodents, it has been shown to decrease stress, anxiety, and fear response, and increase cognition. It is currently not FDA approved, and only a few human trials have used Selank to explore its effects.	Selank has a few complex mechanisms by which it exhibits its anxiolytic effects, and is quite unique in this manner. Predominantly, it has been shown to profoundly increase the expression of brain derived neurotrophic factor (BDNF) in the rodent hippocampal area, which plays roles in neurogenesis, anxiety, and depression. By doing so, selank is somewhat able to mimic the effects of SSRIs, which depend largely on BDNF to exert their action on anxiolysis.\r\n\r\nSelank also has been shown to inhibit the degradation of endogenous enkephalins, a family of opioid peptides in the body. This theoretically allows selank to modulate nociception. In addition to this, selank seems to modulate the GABA receptors in some significant fashion, allowing it to further exhibit its anxiolytic effects, though the exact effect it has on the GABAergic system is not elucidated. Selank may positively allosterically modulate the GABA-A receptors.\r\n\r\nSince it is derived from the immunomodulatory peptide tuftsin, it is somewhat pharmacologically similar in the fact that it enhances immune function. However, this function is secondary to its anxiolytic properties and is not a main goal in the clinical use of selank.	https://pubchem.ncbi.nlm.nih.gov/image/imgsrv.fcgi?cid=11765600&t=l	L-Threonyl-L-lysyl-L-prolyl-N~5~-(diaminomethylene)-L-ornithyl-L-prolylglycyl-L-proline	751.887 g/mol	\N	Anxiety disorders, depression, cognitive enhancement, ADHD, stress management, immune modulation	C33H57N11O9	Selank	\N	\N	\N	\N	\N	\N	\N	\N	\N	\N	\N	\N	\N	\N	\N	\N	\N	f	\N	2025-04-15 02:28:26+00	2026-04-23 01:39:39.818334+00	3.0000	minutes
25	ipamorelin	19	Aib-His-D-2-Nal-D-Phe-Lys-NH2	IPA, Growth hormone secretagogue	Ipamorelin is a synthetic growth hormone releasing peptide (GHRP) that stimulates the release of growth hormone from the pituitary gland. It is considered one of the most selective GHRPs with minimal side effects.	Ipamorelin binds to and activates ghrelin receptors (growth hormone secretagogue receptors) in the pituitary gland, stimulating the natural release of growth hormone. Unlike other GHRPs, it does not significantly affect cortisol or prolactin levels.	https://imagedelivery.net/ey2i3L8oxd4cGMILqBg6mg/c5b1813d-013b-4abc-d06d-a68a571e8900/public	2-amino-2-methylpropanoyl-L-histidyl-D-2-naphthylalanyl-D-phenylalanyl-L-lysinamide	711.85 g/mol	\N	Growth Hormone Deficiency, Anti-Aging, Muscle Building, Bone Density, Sleep Quality	C38H49N9O5	Ipamorelin	\N	\N	\N	\N	\N	\N	\N	\N	\N	\N	\N	\N	\N	\N	\N	\N	\N	f	\N	2025-04-15 02:28:26+00	2026-04-23 01:39:39.818334+00	2.0000	hours
26	cjc-1295	4	Modified GHRH(1-29) with drug affinity complex	CJC-1295 with DAC, Modified GHRH, Growth hormone releasing hormone analog	CJC-1295 is a synthetic analog of growth hormone-releasing hormone (GHRH) that has been modified to increase its half-life and stability. The DAC (Drug Affinity Complex) version provides extended release of growth hormone.	CJC-1295 binds to and activates GHRH receptors on somatotroph cells in the anterior pituitary, stimulating the synthesis and release of growth hormone. The DAC modification extends its half-life to approximately 6-8 days.	https://pubchem.ncbi.nlm.nih.gov/image/imgsrv.fcgi?cid=56841945&t=l	Modified growth hormone releasing hormone (1-29) with maleimidopropionyl-drug affinity complex	3647.28 g/mol	\N	Growth hormone deficiency, anti-aging, muscle wasting, lipodystrophy, metabolic disorders	C165H269N47O46	CJC-1295	\N	\N	\N	\N	\N	\N	\N	\N	\N	\N	\N	\N	\N	\N	\N	\N	\N	f	\N	2025-04-15 02:28:26+00	2026-04-23 01:39:39.818334+00	7.0000	days
27	dsip	13	Trp-Ala-Gly-Gly-Asp-Ala-Ser-Gly-Glu	Delta Sleep-Inducing Peptide, DSIP-9	Delta Sleep-Inducing Peptide (DSIP) is a naturally occurring neuropeptide that promotes deep sleep and regulates sleep-wake cycles. It was first discovered in the cerebral venous blood of rabbits during sleep.	DSIP modulates sleep architecture by influencing delta wave activity in the brain. It affects various neurotransmitter systems including GABA, serotonin, and dopamine, promoting restorative sleep and potentially affecting circadian rhythms.	https://imagedelivery.net/ey2i3L8oxd4cGMILqBg6mg/c5b1813d-013b-4abc-d06d-a68a571e8900/public	L-tryptophyl-L-alanylglycylglycyl-L-aspartyl-L-alanyl-L-serylglycyl-L-glutamic acid	849.83 g/mol	\N	Sleep disorders, insomnia, circadian rhythm disorders, stress management, depression	C35H48N10O15	DSIP	\N	\N	\N	\N	\N	\N	\N	\N	\N	\N	\N	\N	\N	\N	\N	\N	\N	f	\N	2025-04-15 02:28:26+00	2026-04-23 01:39:39.818334+00	8.0000	minutes
100	bpc-157	3	Gly-Glu-Pro-Pro-Pro-Gly-Lys-Pro-Ala-Asp-Asp-Ala-Gly-Leu-Val	Stable gastric pentadecapeptide, Body Protection Compound-157, PL 14736	BPC-157 is a fifteen amino acid long oligopeptide that was discovered during research on human gastric juice. It may have cytoprotective, neuroprotective, and anti-inflammatory effects, and may also accelerate tissue and organ healing.	BPC-157 upregulates VEGF (Vascular Endothelial Growth Factor) and endothelial nitric oxide synthase (eNOS) which enhances blood vessel growth, aiding in wound healing and tissue regeneration. \r\nIt stabilizes cell membranes, reduces oxidative stress, and modulates inflammatory cytokines. Balances nitric oxide signaling by interacting with both NOS (NO synthase) and NO pathways. Downregulates TNF-alpha, IL-6, and other pro-inflammatory mediators. Stimulates fibroblast activity, collagen production, and vascularization.	https://pubchem.ncbi.nlm.nih.gov/image/imgsrv.fcgi?cid=9941957&t=l	\N	1419.5 g/mol	\N	Gastroenterology, Inflammation, Immunology, Tissue Regeneration, Orthopedics, Pulmonology, Cardiovascular disease	C62H98N16O22	BPC-157	\N	\N	\N	\N	\N	\N	\N	\N	\N	\N	\N	\N	\N	\N	\N	\N	\N	f	\N	2025-08-06 20:33:07+00	2026-04-23 01:39:39.818334+00	30.0000	minutes
102	tesamorelin	19	H-Tyr-Ala-Asp-Ala-Ile-Phe-Thr-Asn-Ser-Tyr-Arg-Lys-Val-Leu-Gly-Gln-Leu-Ser-Ala-Arg-Lys-Leu-Leu-Gln-Asp-Ile-Met-Ser-Arg-Gln-Gln-Gly-Gly-Ser-Asn-Gln-Gln-Gly-Glu-Ser-Ser-Leu-Arg-Ala-Arg-Lys-NH2	Egrifta, TH9507, GHRH(1–44) analog	Tesamorelin is a synthetic form of growth-hormone-releasing hormone (GHRH).	Tesamorelin is the N-terminally modified compound based on 44 amino acids sequence of human GHRH. This modified synthetic form is more potent and stable than the natural peptide. It is also more resistant to cleavage by the dipeptidyl aminopeptidase than human GHRH. It binds to GHRH receptor stimulating GH secretion. GH then stimulates IGF-1 secretion in the liver.	https://pubchem.ncbi.nlm.nih.gov/image/imgsrv.fcgi?cid=16137828&t=l	\N	5135.91 g/mol	\N	Growth Hormone Deficiency, Anti-Aging, Muscle Building, Bone Density, Sleep Quality	C221H366N72O67S	Tesamorelin	\N	\N	\N	\N	\N	\N	\N	\N	\N	\N	\N	\N	\N	\N	\N	\N	\N	f	\N	2025-08-07 18:27:56+00	2026-04-23 01:39:39.818334+00	0.5000	hours
103	ll-37	18	\N	LL-37, Cathelicidin LL-37, hCAP18(134–170), CAMP, UNII: 123RUE4YKT, CAS Number: 1312919-56-8	LL-37 is an antimicrobial peptide that plays a crucial role in the human immune system by helping to defend against bacterial infections. It is derived from the cathelicidin antimicrobial peptide (CAMP) gene and is known for its ability to disrupt the membranes of pathogens.	The general rule of the mechanism triggering cathelicidin action, like that of other antimicrobial peptides, involves the disintegration (damaging and puncturing) of cell membranes of organisms toward which the peptide is active. Cathelicidins rapidly destroy the lipoprotein membranes of microbes enveloped in phagosomes after fusion with lysosomes in macrophages. Therefore, LL-37 can inhibit the formation of bacterial biofilms.	https://pubchem.ncbi.nlm.nih.gov/image/imgsrv.fcgi?cid=16198951&t=l	\N	4493.3 g/mol	\N	Dermatology, Immunology	C204H345N61O54	LL-37	\N	\N	\N	\N	\N	\N	\N	\N	\N	\N	\N	\N	\N	\N	\N	\N	\N	f	\N	2025-08-07 19:43:50+00	2026-04-23 01:39:39.818334+00	1.0000	hours
104	ghk-cu	3	\N	Copper peptide	Copper peptide GHK-Cu is a naturally occurring copper complex of the tripeptide glycyl-L-histidyl-L-lysine. The tripeptide has strong affinity for copper(II) and was first isolated from human plasma. It can be found also in saliva and urine. Due to it's short half-life, frequent administration yields far better results than big dosages.	GHK-Cu is a copper-binding tripeptide that promotes tissue repair and regeneration by delivering bioavailable copper to cells and modulating gene expression. It stimulates collagen and elastin production, enhances antioxidant defenses, reduces inflammation, and promotes wound healing and hair growth. By regulating hundreds of genes involved in extracellular matrix remodeling and immune response, GHK-Cu supports skin rejuvenation, reduces scarring, and improves overall tissue health.	https://upload.wikimedia.org/wikipedia/commons/thumb/f/f3/Glycyl-L-histidyl-L-lysine.svg/250px-Glycyl-L-histidyl-L-lysine.svg.png	\N	340.38 g/mol	\N	Dermatology, Physiotherapy, Kinesiology	C14H22CuN6O4	GHK-Cu	\N	\N	\N	\N	\N	\N	\N	\N	\N	\N	\N	\N	\N	\N	\N	\N	\N	f	\N	2025-08-07 21:03:59+00	2026-04-23 01:39:39.818334+00	0.5000	hours
216	ahk-cu	3	AHK-Cu	Copper Tripeptide-3	AHK-Cu is a tripeptide chelated with a divalent copper ion, structurally related to GHK-Cu. Most noted for hair growth stimulative effects.	AHK-Cu works by acting as as a stable copper transporter, increasing Bcl-2:Bax ratio in favor of Bcl-2, suppressing cleaved caspase-3 and PARP, upregulating VEGF and inhibiting TGF-beta1.	https://pubchem.ncbi.nlm.nih.gov/image/imgsrv.fcgi?cid=168431292&t=l	copper;(2S)-6-amino-2-[[(2S)-2-[(2S)-2-azanidylpropanoyl]azanidyl-3-(1H-imidazol-4-yl)propanoyl]amino]hexanoate;hydrochloride	451.39 g/mol	\N	Hair Growth, Scalp Health	C15H24ClCuN6O4	AHK-Cu	\N	\N	\N	\N	\N	\N	\N	\N	\N	\N	\N	\N	\N	\N	\N	\N	\N	f	\N	2026-01-16 22:58:55+00	2026-04-23 01:39:39.818334+00	0.5000	hours
105	dihexa	25	\N	PNB-0408, N-hexanoic-Tyr-Ile-(6) aminohexanoic amide	Dihexa is an oligopeptide drug derived from angiotensin IV. The compound has been found to potently improve cognitive function in animal models of Alzheimer's disease-like mental impairment. In an assay of neurotrophic activity, dihexa was found to be seven orders of magnitude more potent than brain-derived neurotrophic factor.	Dihexa binds with high affinity to hepatocyte growth factor (HGF) and potentiates its activity at its receptor, c-Met	https://upload.wikimedia.org/wikipedia/commons/thumb/4/48/Dihexa.svg/250px-Dihexa.svg.png	\N	504.672 g/mol	\N	Mental Impairment, Cognitive Decline, Neurochemistry, Neurodegenative disease	C27H44N4O5	Dihexa	\N	\N	\N	\N	\N	\N	\N	\N	\N	\N	\N	\N	\N	\N	\N	\N	\N	f	\N	2025-08-08 00:09:49+00	2026-04-23 01:39:39.818334+00	9.0000	hours
106	p21	21	\N	cyclin-dependent kinase inhibitor 1, CDK-interacting protein 1	P21 is a small tetra-peptide derived from the most active region of CNTF (ciliary neurotrophic factor), the amino acid residues 148-151.	P21 binds to and inhibits Cyclin E/CDK2, Cyclin D/CDK4 and CDK6, Cyclin A/CDK2. This inhibition prevents phosphorylation of the retinoblastoma protein (Rb), halting the cell cycle at the G1 phase. G1 arrest allows the cell time to repair DNA damage before continuing to replicate. P21 is reported to slow the progression of neurodegeneration and Alzheimer’s by removing Tau protein build-up and reducing the production of Beta Amyloid plaques.	https://pubchem.ncbi.nlm.nih.gov/image/imgsrv.fcgi?cid=56599151&t=l	\N	578.3 g/mol	\N	Cancer, Anti-Aging, Senescence, Cognitive Decline.	C30H54N65	P21	\N	\N	\N	\N	\N	\N	\N	\N	\N	\N	\N	\N	\N	\N	\N	\N	\N	f	\N	2025-08-08 00:54:52+00	2026-04-23 01:39:39.818334+00	45.0000	minutes
107	ara-290	18	Pyr-Glu-Gln-Leu-Glu-Arg-Ala-Leu-Asn-Ser-Ser-NH₂	PHBSP, pHBSP peptide, Pyroglutamate helix B surface peptide, Cibinetide	Ara-290 is a synthetic peptide derived from erythropoietin (EPO), specifically from the B-helix region of the EPO molecule. It was engineered to retain tissue-protective and anti-inflammatory properties without stimulating erythropoiesis (red blood cell production), which is a key function of full-length EPO.	Ara-290 does not activate the classical erythropoietic receptor (EPOR-EPOR homodimer), Instead, it binds to the IRR (EPOR-CD131 heterodimer), triggering anti-inflammatory, anti-apoptotic, and pro-regenerative responses. This makes it ideal for use in tissue protection and regeneration without increasing hematocrit or causing thrombosis.	https://upload.wikimedia.org/wikipedia/commons/thumb/9/96/Cibinetide.svg/330px-Cibinetide.svg.png	\N	1257.324 g/mol	\N	Neuropathic pain, Neurology, Autoimmune disease, Chronic Inflammation, Ischemia/reperfusion injury	C51H84N16O21	ARA-290	\N	\N	\N	\N	\N	\N	\N	\N	\N	\N	\N	\N	\N	\N	\N	\N	\N	f	\N	2025-08-08 05:11:11+00	2026-04-23 01:39:39.818334+00	20.0000	minutes
112	igf-1-lr3	4	\N	Long arginine 3-IGF-1, LR3-IGF-1	IGF-1 LR3 retains the pharmacological activity of IGF-1 as an agonist of the IGF-1 receptor, has very low affinity for the IGFBP's and has improved metabolic stability. As a result, it is approximately three times more potent than IGF-1, and possesses a significantly longer half-life of about 20–30 hours.	IGF-1 LR3 binds to the IGF-1 receptor. Once IGF-1R is activated, two primary signaling pathways are stimulated. This has effects mainly through two pathways:\r\n1. PI3K–AKT Pathway: Promotes glucose uptake (like insulin), Inhibits apoptosis (cell death), Enhances protein synthesis and cell growth, Encourages muscle hypertrophy\r\n2. RAS–RAF–MAPK Pathway: Stimulates cell proliferation, Promotes cell differentiation, Plays a role in tissue regeneration and repair\r\n\r\nIGF-1 LR3 is designed to resist binding to IGFBPs, especially IGFBP-3 and IGFBP-5.\r\nNative IGF-1 is 95% bound to IGFBPs, limiting bioavailability. The R3 substitution and 13 amino acid N-terminal extension make LR3 more bioavailable and longer-lasting in circulation.	https://pub.mdpi-res.com/biomolecules/biomolecules-11-00217/article_deploy/html/images/biomolecules-11-00217-g001.png?1612433893=	\N	9117.60 g/mol	\N	Anti-Aging, Muscle Building, Bone Density	C400H625N111O115S9	IGF-1 LR3	\N	\N	\N	\N	\N	\N	\N	\N	\N	\N	\N	\N	\N	\N	\N	\N	\N	f	\N	2025-08-13 12:30:29+00	2026-04-23 01:39:39.818334+00	25.0000	hours
128	igf-1-des	3	Gly-Arg-Gly-Ala-Ser-Gly-Gly-Ser-Gly-Gly	Des(1‑3) IGF‑1, Insulin‑like growth factor‑1 des‑(1‑3), 4‑70 insulin‑like growth factor‑1	IGF‑1 DES is a naturally occurring truncated analogue of IGF‑1, lacking the first three N‑terminal amino acids Gly‑Pro‑Glu. It has heightened biological potency, being around 10‑fold more effective than full-length IGF‑1 in stimulating cellular hypertrophy and proliferation due to greatly reduced binding to IGF binding proteins.	IGF‑1 DES binds to the IGF‑1 receptor with higher affinity and evades inhibition by IGFBPs, resulting in enhanced receptor-mediated signaling. Upon receptor activation, it triggers key anabolic pathways - PI3K/Akt and mTOR, promoting muscle protein synthesis, cell growth, and survival. With a shorter half-life of approx. 20–30 minutes, it’s especially suited for site-specific delivery, offering high local potency with reduced systemic exposure.	https://www.peptidesciences.com/media/wysiwyg/igf1-des.png	\N	7371.48 g/mol	\N	Neurology, Muscle Growth, Tissue Repair	C319H495N91O96S7	IGF-1 DES	\N	\N	\N	\N	\N	\N	\N	\N	\N	\N	\N	\N	\N	\N	\N	\N	\N	f	\N	2025-08-26 02:02:56+00	2026-04-23 01:39:39.818334+00	5.0000	minutes
114	ss-31	20	D‑Arg‑Dmt‑Lys‑Phe‑NH₂	Elamipretide, Bendavia, MTP-131	SS-31 is a small mitochondrially-targeted tetrapeptide that appears to reduce the production of toxic reactive oxygen species and stabilize cardiolipin.	It localizes to the inner mitochondrial membrane and selectively binds cardiolipin. Binding to cardiolipin stabilizes it, enhancing ETC and scavenging ROS.	https://upload.wikimedia.org/wikipedia/commons/thumb/7/7b/Elamipretide_structure.svg/250px-Elamipretide_structure.svg.png	(2S)-6‑Amino‑2‑[[(2S)-2‑[[(2R)-2‑amino‑5‑(diaminomethylideneamino)pentanoyl]amino]‑3‑(4‑hydroxy‑2,6‑dimethylphenyl)propanoyl]amino]‑N‑[(2S)-1‑amino‑1‑oxo‑3‑phenylpropan‑2‑yl]hexanamide	639.8 g/mol	\N	Mitochondria, Neurodegenerative disorders, Kidney disease models, Heart Failure, Aging	C32H49N9O5	SS-31	\N	\N	\N	\N	\N	\N	\N	\N	\N	\N	\N	\N	\N	\N	\N	\N	\N	f	\N	2025-08-14 23:04:41+00	2026-04-23 01:39:39.818334+00	2.0000	hours
115	aod-9604	19	Tyr‑Leu‑Arg‑Ile‑Val‑Gln‑Cys‑Arg‑Ser‑Val‑Glu‑Gly‑Ser‑Cys‑Gly‑Phe	\N	AOD9604 is a synthetic 16-amino-acid peptide derived from the C-terminal domain of human growth hormone, with an extra tyrosine at the N-terminus for stabilization.	AOD9604 retains the lipolytic effects of hGH but does not stimulate IGF‑1 production, nor does it trigger systemic growth effects. Evidence from animal studies suggests AOD9604 activates lipolytic pathways, increasing breakdown of stored triglycerides into free fatty acids and glycerol, possibly via hormone‑sensitive lipase activation and enhanced cAMP–PKA signaling. It may suppress the formation of new fat — potentially by interfering with key enzymes like acetyl-CoA carboxylase. Studies in obese mice show AOD9604 may upregulate β₃‑adrenergic receptor expression, thereby enhancing sensitivity of adipose tissue to adrenergic lipolytic stimuli. Notably, even in β₃‑AR knockout mice, some lipolytic effects persist, indicating additional mechanisms beyond this pathway. AOD9604 showed promise in osteoarthritis models by supporting cartilage structure, proteoglycan production, and anti-inflammatory pathways.	https://upload.wikimedia.org/wikipedia/commons/thumb/3/31/AOD_9604.svg/330px-AOD_9604.svg.png	L-Tyrosyl-L-leucyl-L-arginyl-L-isoleucyl-L-valyl-L-glutaminyl-L-cystinyl-L-arginyl-L-seryl-L-valyl-L-glutamyl-L-glycyl-L-seryl-L-cystinyl-L-glycyl-L-phenylalanine, cyclic (7→14)-disulfide	1,815 g/mol	\N	Obesity, Insulin Resistance, Osteoarthritis	C78H123N23O22S2	AOD-9604	\N	\N	\N	\N	\N	\N	\N	\N	\N	\N	\N	\N	\N	\N	\N	\N	\N	f	\N	2025-08-19 19:19:00+00	2026-04-23 01:39:39.818334+00	0.7500	hours
117	ace-031	19	Ala‑Trp‑Arg‑Gln‑Asn‑Thr‑Arg‑Tyr‑Ser‑Arg‑Ile‑Glu‑Ala‑Ile‑Lys‑Ile‑Gln‑Ile‑Leu‑Ser‑Lys‑Leu‑Arg‑Leu‑NH₂	\N	ACE‑031 is a fusion protein composed of the extracellular domain of human activin receptor type IIB linked to an IgG1 Fc region.	ACE‑031 acts as a decoy receptor, binding myostatin (and activin A), preventing their interaction with native ActRIIB on muscle cells. This blocks the inhibitory signaling that restricts muscle growth, enabling increased muscle protein synthesis and hypertrophy. In mice, ACE‑031 resulted in ~16% greater body weight gain versus controls after 4 weeks, indicating broad muscle hypertrophy across fiber types.	https://pubchem.ncbi.nlm.nih.gov/image/imgsrv.fcgi?cid=118732224&t=l	\N	2956.49 g/mol	\N	Atrophy, Muscle Wasting, Bodybuilding, Weight Loss	C122H227N42O22	ACE-031	\N	\N	\N	\N	\N	\N	\N	\N	\N	\N	\N	\N	\N	\N	\N	\N	\N	f	\N	2025-08-20 00:54:57+00	2026-04-23 01:39:39.818334+00	12.5000	days
118	pe-22-28	21	Gly-Val-Ser-Trp-Gly-Leu-Arg	\N	PE‑22‑28 is a synthetic analog of spadin, a peptide derived from sortilin. The segment corresponds to amino acid residues 22–28 of spadin.	PE-22-28 inhibits TREK-1, a channel involved in regulating mood, neuroplasticity, and neuronal excitability. TREK-1 inhibition is linked to antidepressant effects.	https://www.peptideswiki.org/wp-content/uploads/2023/01/PE-22-28.png	(2S)-2-{[(2S)-2-{[(2S)-2-{[(2S)-2-{[(2S)-2-{[(2S)-2-amino-3-hydroxypropionyl]amino}-3-(1H-indol-3-yl)propanoyl]amino}-2-[(1-methylethyl)amino]-2-oxoethyl]amino}-3-hydroxypropanoyl]amino}-3-methylbutanoyl]amino}acetamide	773.9 g/mol	\N	Depression, Studying aid, Neuroprotection	C22H52N10O8	PE-22-28	\N	\N	\N	\N	\N	\N	\N	\N	\N	\N	\N	\N	\N	\N	\N	\N	\N	f	\N	2025-08-21 01:30:58+00	2026-04-23 01:39:39.818334+00	\N	\N
119	pnc-27	20	H-Gly-Ser-Ile-Asn-Gln-Gln-Gln-Ser-Ser-Lys-Leu-Gln-Thr-Phe-Ser-Asp-Leu-Trp-Lys-Leu-Leu-NH₂	\N	PNC‑27 is a 32-residue chimeric peptide that combines p53-derived HDM‑2-binding domain and cell-penetrating peptide (CPP) leader sequence from the Drosophila antennapedia homeodomain.	PNC‑27 selectively binds to HDM‑2 when it is overexpressed in the plasma membranes of cancer cells, but is minimally present in normal cell membranes. This interaction is essential for its selective cytotoxicity, as confirmed by experiments using HDM‑2-specific antibodies that block PNC‑27 killing effects. Once bound to membrane HDM‑2, PNC‑27 organizes into oligomeric, ring-shaped pores on the cancer cell membrane, leading to necrosis rather than apoptosis. Beyond plasma membrane damage, PNC‑27 enters the cancer cell and localizes to mitochondria, disrupting mitochondrial integrity and function, which contributes to cell death. PNC‑27 induces necrosis even in p53-null cancer cells (e.g., K562 leukemia), indicating its effectiveness is independent of p53 status.	https://peptide-products.com/images/products/pnc-27-structure.jpg	\N	4031.73 g/mol	\N	Cancer, Immunology	C188H292N52O44S	PNC-27	\N	\N	\N	\N	\N	\N	\N	\N	\N	\N	\N	\N	\N	\N	\N	\N	\N	f	\N	2025-08-21 01:51:36+00	2026-04-23 01:39:39.818334+00	2.0000	hours
121	ghrp-6	4	His-D-Trp-Ala-Trp-D-Phe-Lys-NH₂	growth hormone-releasing hexapeptide	GHRP-6 also known as growth hormone-releasing hexapeptide is a synthetic growth hormone releasing peptide (GHRP) that stimulates the release of growth hormone from the pituitary gland. GHRP-6 has a lower prolactin/cortisol spike compared to GHRP-2, making it better tolerated long-term.	GHRP-6 binds to GHS-R1a receptors in the hypothalamus and pituitary. This stimulates pulsatile release of GH and appetite. This causes indirect IGF-1 release via GH-mediated liver stimulation.	https://upload.wikimedia.org/wikipedia/commons/thumb/e/e6/GHRP-6.png/250px-GHRP-6.png	\N	873.01 g/mol	\N	Growth Hormone Deficiency, Anti-Aging, Muscle Building, Bone Density, Sleep Quality, Appetite Deficiency	C46H56N12O6	GHRP-6	\N	\N	\N	\N	\N	\N	\N	\N	\N	\N	\N	\N	\N	\N	\N	\N	\N	f	\N	2025-08-21 16:56:28+00	2026-04-23 01:39:39.818334+00	0.3800	hours
122	ghrp-2	4	D-Ala-D-(β-naphthyl)-Ala-Trp-D-Phe-Lys-NH2	Pralmorelin, GHRP Kaken 100, KP-102, GPA-748, WAY-GPA-748, pralmorelin hydrochloride, pralmorelin dihydrochloride, growth hormone-releasing peptide 2	GHRP-2 also known as Pralmorelin is an orally active, synthetic growth hormone releasing peptide (GHRP), specifically, an analogue of met-enkephalin, that stimulates the release of growth hormone from the pituitary gland. It is marketed by Kaken Pharmaceutical in Japan in a single-dose formulation for the assessment of growth hormone deficiency.	GHRP-2 binds to GHS-R receptors. This stimulates pulsatile release of GH and appetite. This causes indirect IGF-1 release via GH-mediated liver stimulation. It is more potent than GHRP-6 and less hunger-inducing than GHRP-6.	https://upload.wikimedia.org/wikipedia/commons/thumb/a/ac/Pralmorelin.svg/250px-Pralmorelin.svg.png	(2S)-6-Amino-2-[[(2S)-2-[[(2S)-2-[[(2S)-2-[[(2R)-2-[[(2R)-2-aminopropanoyl]amino]-3-naphthalen-2-ylpropanoyl]amino]propanoyl]amino]-3-(1H-indol-3-yl)propanoyl]amino]-3-phenylpropanoyl]amino]hexanamide	817.992 g/mol	\N	Growth Hormone Deficiency, Anti-Aging, Muscle Building, Bone Density, Sleep Quality, Appetite Deficiency	C45H55N9O6	GHRP-2	\N	\N	\N	\N	\N	\N	\N	\N	\N	\N	\N	\N	\N	\N	\N	\N	\N	f	\N	2025-08-22 00:29:41+00	2026-04-23 01:39:39.818334+00	0.3800	hours
173	hexarelin	19	His-D-2-methyl-Trp-Ala-Trp-D-Phe-Lys-NH2	Examorelin, EP-23905, MF-6003	Hexarelin is a synthetic hexapeptide. It is part of the class of growth hormone releasing peptides derived from GHRP-6 analogs and acts as a growth hormone secretagogue. It is not structurally similar to the endogenous hormone ghrelin, but mimics some of ghrelin’s effects via the ghrelin receptor.	Hexarelin binds to the ghrelin receptor in the hypothalamus and pituitary, stimulating GH release. It can potentiate GH secretion beyond what GH-releasing hormone alone can do, and shows synergistic effects with GHRH in some settings. Some experiments suggest that hexarelin might also trigger an unknown hypothalamic factor in addition to direct and indirect effects in stimulating GH. It may also inhibit angiotensin converting enzyme.	https://pubchem.ncbi.nlm.nih.gov/image/imgsrv.fcgi?cid=6918297&t=l	(2S)-6-amino-2-[[(2R)-2-[[(2S)-2-[[(2S)-2-[[(2R)-2-[[(2S)-2-amino-3-(1H-imidazol-5-yl)propanoyl]amino]-3-(2-methyl-1H-indol-3-yl)propanoyl]amino]propanoyl]amino]-3-(1H-indol-3-yl)propanoyl]amino]-3-phenylpropanoyl]amino]hexanamide	887.059 g/mol	\N	Growth Hormone Deficiency, Anabolism, Performance Enhancement, Regeneration, Fibrosis	C47H58N12O6	Hexarelin	\N	\N	\N	\N	\N	\N	\N	\N	\N	\N	\N	\N	\N	\N	\N	\N	\N	f	\N	2025-10-05 09:56:00+00	2026-04-23 01:39:39.818334+00	1.5000	hours
123	peg-mgf	3	Tyr‑Gln‑Pro‑Pro‑Ser‑Thr‑Asn‑Lys‑Asn‑Thr‑Lys‑Ser‑Gln‑Arg‑Arg‑Lys‑Gly‑Ser‑Thr‑Phe‑Glu‑Glu‑Arg‑Lys–NH₂	Pegylated Mechano Growth Factor	PEG-MGF is a modified form of Mechano Growth Factor, a splice variant of IGF-1, designed for greater stability and systemic effect.	After muscle damage or overload, your body produces IGF-1, which can be spliced into MGF. MGF stimulates satellite cell activation and muscle repair, essentially telling the muscle to grow and regenerate. Natural MGF acts locally and degrades quickly — PEG-MGF allows for systemic circulation and longer-lasting effects.	https://www.genemedics.com/wp-content/uploads/2021/05/Pegylated-Mechano-Growth-Factor-1024x642.jpg	Poly(ethylene glycol)-conjugated IGF‑1 Ec splice variant peptide	2867–2888 g/mol	\N	Muscle growth, Muscle Recovery, Performance, Bone repair, Tendon repair	C121H200N42O39	PEG-MGF	\N	\N	\N	\N	\N	\N	\N	\N	\N	\N	\N	\N	\N	\N	\N	\N	\N	f	\N	2025-08-22 00:51:35+00	2026-04-23 01:39:39.818334+00	50.0000	hours
174	mgf	28	Tyr‑Gln‑Pro‑Pro‑Ser‑Thr‑Asn‑Lys‑Asn‑Thr‑Lys‑Ser‑Gln‑Arg‑Arg‑Lys‑Gly‑Ser‑Thr‑Phe‑Glu‑Glu‑Arg‑Lys–NH₂	INSULIN-LIKE GROWTH FACTOR 1-EC PEPTIDE, IGF-1-EC, MECHANO GROWTH FACTOR	MGF is an alternatively spliced variant of insulin-like growth factor-I presenting a unique C-terminal modification. Due to this unique C-terminal, MGF is exceptionally good at stimulating muscle tissue stem cells and their activation.	After muscle damage or overload, your body produces IGF-1, which can be spliced into MGF. MGF stimulates satellite cell activation and muscle repair, essentially telling the muscle to grow and regenerate. Natural MGF acts locally and degrades quickly, but produces significant localized growth.	\N	IGF‑1 Ec splice variant peptide	2867–2888 g/mol	\N	Muscle growth, Muscle Recovery, Performance, Tendon repair	C121H200N42O39	MGF	\N	\N	\N	\N	\N	\N	\N	\N	\N	\N	\N	\N	\N	\N	\N	\N	\N	f	\N	2025-10-05 10:58:46+00	2026-04-23 01:39:39.818334+00	7.0000	minutes
124	foxo4-dri	20	H‑D‑Leu‑D‑Thr‑D‑Leu‑D‑Arg‑D‑Lys‑D‑Glu‑D‑Pro‑D‑Ala‑D‑Ser‑D‑Glu‑D‑Ile‑D‑Ala‑D‑Gln‑D‑Ser‑D‑Ile‑D‑Leu‑D‑Glu‑D‑Ala‑D‑Tyr‑D‑Ser‑D‑Gln‑D‑Asn‑Gly‑D‑Trp‑D‑Ala‑D‑Asn‑D‑Arg‑D‑Arg‑D‑Ser‑D‑Gly‑D‑Gly‑D‑Lys‑D‑Arg‑D‑Pro‑D‑Pro‑D‑Pro‑D‑Arg‑D‑Arg‑D‑Arg‑D‑Gln‑D‑Arg‑D‑Arg‑D‑L	\N	FOXO4-DRI is a novel peptide designed specifically to target and eliminate senescent cells, playing a critical role in aging and age-related diseases. Derived from the FOXO4 protein, this peptide has attracted significant attention due to its potential for promoting healthy aging, improving tissue regeneration, and extending lifespan.	FOXO4‑DRI is engineered to disrupt the interaction between the transcription factor FOXO4 and p53 in senescent cells. This leads to p53 nuclear exclusion, directing it to mitochondria and activation of p53-dependent apoptosis, selectively eliminating senescent cells.\r\nThe D-retro-inverso design imparts high stability and resistance to degradation, making FOXO4‑DRI effective in cellular environments	https://pubchem.ncbi.nlm.nih.gov/image/imgsrv.fcgi?cid=167312269&t=l	\N	5358.06 g/mol	\N	Senescence, Cartilage Degeneration, Hypogonadism, Inflammation	C228H488N86O64	FOXO4-DRI	\N	\N	\N	\N	\N	\N	\N	\N	\N	\N	\N	\N	\N	\N	\N	\N	\N	f	\N	2025-08-22 01:16:19+00	2026-04-23 01:39:39.818334+00	5.0000	hours
125	b7-33	27	Val-Ile-Lys-Leu-Ser-Gly-Arg-Glu-Leu-Val-Arg-Ala-Gln-Ile-Ala-Ile-Ser-Gly-Met-Ser-Thr-Trp-Ser-Lys-Arg-Ser-Leu-NH2	GTPL9321, (B7-33)H2	B7‑33 is a synthetic peptide derived from the B‑chain of human relaxin‑2. It’s designed to mimic the hormone’s beneficial effects, particularly anti‑fibrotic and vasoprotective actions while, offering improved stability and a more selective signaling profile.	B7‑33 acts as a functionally selective agonist for the relaxin family peptide receptor 1 (RXFP1). Unlike H2 relaxin, which activates both cAMP-PKA and pERK (MAPK) pathways, B7‑33 preferentially activates the pERK pathway, minimizing cAMP-mediated effects that can include hormonal side effects or tumor promotion. Through ERK activation, B7‑33 stimulates MMP‑2 expression and promotes collagen degradation, aiding tissue remodeling and reducing fibrosis.	https://file.medchemexpress.eu/product_pic/hy-p10728.gif	\N	2,986.54 g/mol	\N	Endothelial Health, Cardioprotection, Fibrosis, Implants	C131H229N41O36S	B7-33	\N	\N	\N	\N	\N	\N	\N	\N	\N	\N	\N	\N	\N	\N	\N	\N	\N	f	\N	2025-08-22 01:38:38+00	2026-04-23 01:39:39.818334+00	0.7500	hours
126	mots-c	19	Met-Arg-Trp-Gln-Glu-Met-Gly-Tyr-Ile-Phe-Tyr-Pro-Arg-Lys-Leu-Arg	Mitochondrial Open Reading Frame of the 12S rRNA-c	MOTS‑c is a 16‑amino‑acid peptide encoded within mitochondrial DNA. It is increasingly recognized for its role as a mitochondrial‑derived signaling peptide that regulates metabolism, insulin sensitivity, stress responses, and aging earning it the label of an “exercise mimetic”	MOTS‑c suppresses the folate cycle, reducing levels of 5‑Me‑THF, which in turn impairs de novo purine synthesis -leading to accumulation of AICAR. AICAR: activates AMPK, increases GLUT4 expression and glucose uptake, suppresses acetyl-CoA carboxylase, promoting fatty acid oxidation, stimulates mitochondrial biogenesis via PGC‑1α activation. In mouse models, MOTS‑c improves glucose tolerance and prevents age-related or high-fat diet–induced insulin resistance and obesity without affecting food intake. These effects are especially pronounced in skeletal muscle, emphasizing its role in enhancing insulin action via AMPK-mediated pathways. MOTS-c promotes mitochondrial biogenesis, enhances mitochondrial fusion, and upregulates mitophagy-related genes like PINK1 and PARK2. In MRSA‑induced sepsis models, MOTS‑c enhances survival, reduces bacterial load, and shifts cytokine balance towards anti-inflammatory, while suppressing MAPK signaling and boosting AhR and STAT3 in macrophages.	https://pubchem.ncbi.nlm.nih.gov/image/imgsrv.fcgi?cid=146675088&t=l	L-methionyl-L-arginyl-L-tryptophyl-L-glutaminyl-L-glutamyl-L-methionyl-L-glycyl-L-tyrosyl-L-isoleucyl-L-phenylalanyl-L-tyrosyl-L-prolyl-L-arginyl-L-lysyl-L-leucyl-L-arginine	2177.57 g/mol	\N	Mitochondrial function, Immunology, Cardiovascular Health, Insulin Resistance	C99H160N25O24S2	MOTS-c	\N	\N	\N	\N	\N	\N	\N	\N	\N	\N	\N	\N	\N	\N	\N	\N	\N	f	\N	2025-08-23 02:18:22+00	2026-04-23 01:39:39.818334+00	10.0000	minutes
129	survodutide	19	H‑His‑{Ac4c}‑Gln‑Gly‑Thr‑Phe‑Thr‑Ser‑Asp‑Tyr‑Ser‑Lys‑Tyr‑Leu‑Asp‑Glu‑Arg‑Ala‑Ala‑Lys‑Asp‑Phe‑Ile‑{GGSGSG‑γE‑C18‑diacid}‑Trp‑Leu‑Glu‑Ser‑Ala‑NH₂	EX‑A7878, BI‑456906	Survodutide is an experimental peptide that works as a dual glucagon/GLP-1 receptor agonist. Unlike other dual GLP-1/glucagon dual agonists, it is a glucagon analog rather than an analog of oxyntomodulin. The design includes a C18 fatty diacid chain, which promotes albumin binding, thereby significantly extending its half-life for once-weekly administration	GLP‑1R activation reduces appetite, enhances insulin secretion, delays gastric emptying, and improves glycemic control.\r\nGCGR activation increases energy expenditure, promotes lipolysis, and enhances fat metabolism, therefore helping preserve lean mass.\r\nThe peptide is acylated with a C18 fatty diacid moiety, enabling strong albumin binding and prolonged half‑life of around 109 to 115 hours, supporting once‑weekly subcutaneous administration.\r\nIt includes a non‑coded amino acid (Ac4c) at position 2, conferring resistance to DPP‑4 degradation.	https://pubchem.ncbi.nlm.nih.gov/image/imgsrv.fcgi?cid=168429725&t=l	\N	4231.6 g/mol	\N	Obesity, Type 2 Diabetes, Steatohepatitis,	C192H289N47O61	Survodutide	\N	\N	\N	\N	\N	\N	\N	\N	\N	\N	\N	\N	\N	\N	\N	\N	\N	f	\N	2025-08-26 02:13:49+00	2026-04-23 01:39:39.818334+00	6.0000	days
127	mazdutide	19	His-{Aib}-Gln-Gly-Thr-Phe-Thr-Ser-Asp-Tyr-Ser-Lys-Tyr-Leu-Asp-Glu-Lys-Lys-Ala-Lys-{AEEA-AEEA-γGlu‑Nonadecanoic acid}-Glu-Phe-Val-Glu-Trp-Leu-Leu-Glu-Gly-Gly-Pro-Ser-Ser-Gly‑NH₂	IBI‑362, LY‑3305677	Mazdutide is a long‑acting dual agonist targeting GLP‑1 receptor and Glucagon receptor. It is a synthetic analogue of the gut hormone oxyntomodulin, engineered for extended action via a fatty‑acid side chain conjugation.	By agonizing GLP-1 and Glucagon receptors it promotes glucose‑dependent insulin secretion, reduces appetite, and slows gastric emptying, boosts energy expenditure, enhances fat metabolism, and reduces hepatic fat.	https://structimg.guidechem.com/7/31/16995030.png	\N	4563.1 g/mol	\N	Insulin Resistance, Obesity, Addiction	C210H322N46O67	Mazdutide	\N	\N	\N	\N	\N	\N	\N	\N	\N	\N	\N	\N	\N	\N	\N	\N	\N	f	\N	2025-08-23 02:56:01+00	2026-04-23 01:39:39.818334+00	6.0000	days
116	semaglutide	19	His‑Aib‑Glu‑Gly‑Thr‑Phe‑Thr‑Ser‑Asp‑Val‑Ser‑Ser‑Tyr‑Leu‑Glu‑Gly‑Gln‑Ala‑Ala‑Lys(AEEAc‑AEEAc‑γ‑Glu‑17‑carboxyheptadecanoyl)‑Glu‑Phe‑Ile‑Ala‑Trp‑Leu‑Val‑Arg‑Gly‑Arg‑Gly‑OH	\N	Semaglutide is a GLP‑1 receptor agonist, mimicking endogenous GLP‑1.	Semaglutide stimulates glucose-dependent insulin secretion, suppresses glucagon release, delays gastric emptying, reducing appetite and overall energy intake.	https://upload.wikimedia.org/wikipedia/commons/thumb/0/0e/Semaglutid_3Letter.svg/500px-Semaglutid_3Letter.svg.png	\N	4113.64 g/mol.	\N	Obesity, Insulin resistance, Recomposition	C187H291N45O59	Semaglutide	\N	\N	\N	\N	\N	\N	\N	\N	\N	\N	\N	\N	\N	\N	\N	\N	\N	f	\N	2025-08-20 00:37:55+00	2026-04-23 01:39:39.818334+00	6.5000	days
208	cagrilintide	19	XKCNTATCATQRLAEFLRHSSNNFGPILPPTNVGSNTP	GLXC-26801	Cagrilintide is a long-acting analogue of amylin used for obesity and Type 2 Diabetes.	Cagrilintide is a long-acting analog of amylin which is co-secreted with insulin by pancreatic beta-cells. It works by slowing down gastric emptying, promoting satiety, inhibiting digestive secretion and inhibiting glucagon secretion. This results in reduced food intake and reduced glucose synthesis. It is especially beneficial if combined with GLP-1 inhibitors like semaglutide or tirzepatide for obesity, SGLT2 inhibitors like Canaglifozin for Diabetes.	https://pubchem.ncbi.nlm.nih.gov/image/imgsrv.fcgi?cid=167312356&t=l	\N	4409 g/mol	\N	Obesity, Insulin Resistance	C194H312N54O59S2	Cagrilintide	\N	\N	\N	\N	\N	\N	\N	\N	\N	\N	\N	\N	\N	\N	\N	\N	\N	f	\N	2025-12-14 23:36:52+00	2026-04-23 01:39:39.818334+00	7.0000	days
213	tirzepatide	19	YXEGTFTSDYSIXLDKIAQKAFVQWLIAGGPSSGAPPPS	Mounjaro, Zepbound, LY3298176	Tirzepatide is a peptide used for treatment of type 2 diabetes and obesity.	Tirzepatide is an agonist of GLP-1 and GIP. It has a very large preference for GIP which makes it far more tolerable and decreases GLP-1 catabolism very significantly. Unlike GLP-1, GIP can be agonized with an extreme degree unlike GLP-1.	\N	\N	4813.527 g/mol	\N	Obesity, Body Recomposition, Type 2 Diabetes, Obstructive Sleep Apnea	C225H348N48O68	Tirzepatide	\N	\N	\N	\N	\N	\N	\N	\N	\N	\N	\N	\N	\N	\N	\N	\N	\N	f	\N	2025-12-19 00:28:49+00	2026-04-23 01:39:39.818334+00	5.0000	days
130	thymosin-alpha-1	18	Ac-Ser-Asp-Ala-Ala-Val-Asp-Thr-Ser-Ser-Glu-Ile-Thr-Thr-Lys-Asp-Leu-Lys-Glu-Lys-Lys-Glu-Val-Val-Glu-Glu-Ala-Glu-Asn-OH	thymalfasin	Thymosin α1 is a 28‑amino‑acid bioactive peptide, biologically derived from the N‑terminus of prothymosin α, and originally isolated from thymus tissue. The synthetic form, thymalfasin, is approved in over 30–35 countries for clinical use, notably against chronic hepatitis B and C, and as an immune enhancer	Tα1 enhances the maturation and differentiation of T cells, dendritic cells, and natural killer cells, and stimulates antibody production. It interacts with TLR2, TLR3, TLR4, TLR7, and TLR9, triggering downstream signaling via MyD88, NF‑κB, IRF3, MAPK, and TRAF6 to boost cytokine production and antigen presentation. Tα1 enhances levels of glutathione and activity of antioxidant enzymes, helping to mitigate oxidative stress and support tissue protection Tα1 promotes immunosurveillance via increased MHC expression, and in preclinical models, inhibits tumor growth, metastasis, and improves survival, especially when combined with chemotherapy or as adjuvant therapy.	https://pubchem.ncbi.nlm.nih.gov/image/imgsrv.fcgi?cid=16130571&t=l	(2S)-N-[(2S)-2-{[(2S)-2-{[(2S)-2-{…}]}]}]-28-amino acid chain with N-terminal acetyl group and C-terminal L-asparagine	3,108 g/mol	\N	Viral Infections, Immunodeficiency, Sepsis & Critical Illness, Oncology, Autoimmune/Inflammatory.	C129H215N33O55	Thymosin Alpha-1	\N	\N	\N	\N	\N	\N	\N	\N	\N	\N	\N	\N	\N	\N	\N	\N	\N	f	\N	2025-08-27 03:13:31+00	2026-04-23 01:39:39.818334+00	2.0000	hours
132	astressin-b	4	Ac-Asp-Leu-Ser-D-Phe-His-D-aMeLeu-Leu-Arg-Lys-Nle-Ile-Glu-Ile-Glu-Lys-Gln-Glu-Lys-Glu-Lys-Glu-Glu-Ala-DL-Glu(1)-D-Asn-Asn-Lys(1)-Leu-Leu-Leu-Asp-D-aMeLeu-Ile-NH2	\N	Astressin‑B is a synthetic peptide designed as a corticotropin-releasing factor receptor antagonist. It has been studied in preclinical models for its potential to modulate stress responses, particularly in conditions related to the hypothalamic–pituitary–adrenal axis.	By inhibiting CRF receptors, Astressin-B potently reduces stress-induced release of ACTH and cortisol. Studies in animal models have shown effects such as reduced anxiety-like behavior, amelioration of stress-related physiological changes, and modulation of gastric motility. Astressin-B is able to delay the emptying of solid food in mice. Astressin-B can prevent the release of adrenocorticotropic hormone in mice due to shock, alcohol and endotoxemia. Treatment with astressin-B caused the sudden growth of hair in mice bred to overexpress CRF.	https://pubchem.ncbi.nlm.nih.gov/image/imgsrv.fcgi?cid=73350132&t=l	Ac-Asp-Leu-Ser-D-Phe-His-D-aMeLeu-Leu-Arg-Lys-Nle-Ile-Glu-Ile-Glu-Lys-Gln-Glu-Lys-Glu-Lys-Glu-Glu-Ala-DL-Glu(1)-D-Asn-Asn-Lys(1)-Leu-Leu-Leu-Asp-D-aMeLeu-Ile-NH2	4044 g/mol	\N	Obesity, Sexual Health, Stress Management, Gastrointestinal Dysregulation, Hair loss, PTSD, Anxiety	C183H305N47O55	Astressin-B	\N	\N	\N	\N	\N	\N	\N	\N	\N	\N	\N	\N	\N	\N	\N	\N	\N	f	\N	2025-08-27 21:03:34+00	2026-04-23 01:39:39.818334+00	2.5000	hours
134	epitalon	24	Ala–Glu–Asp–Gly	Epithalamin	Epitalon is a synthetic tetrapeptide derived from pineal gland extract also known as epithalamin. It is noted for its anti-aging effects and was extensively studied at the St. Petersburg Institute of Bioregulation and Gerontology under Khavinson’s supervision. Its one of the most researched Khav peptides which were all researched under Khavinson's supervision.	Epitalon induces telomerase activity, leading to telomere elongation in human somatic cells, potentially extending cellular lifespan and bypassing replicative senescence. It binds to histones,especially H1/3 and H1/6, modulating chromatin structure and promoting gene expression tied to neurogenesis and cellular rejuvenation. It enhances antioxidant enzyme activity and shows potential in reducing tumor development and metastasis in animal models. Improves melatonin secretion and normalizes circadian rhythm, with broader neuroendocrine regulatory roles.	https://pubchem.ncbi.nlm.nih.gov/image/imgsrv.fcgi?cid=219042&t=l	(4S)-4-[[(2S)-2‑aminopropanoyl]amino]-5‑[[(2S)-3‑carboxy-1‑(carboxymethylamino)-1‑oxopropan-2‑yl]amino]-5‑oxopentanoic acid	390.35 g/mol	\N	Anti-Aging, Neurology, Neurodegeneration, Endocrine Regulation, Circadian Regulation, Gerontology	C14H22N4O9	Epitalon	\N	\N	\N	\N	\N	\N	\N	\N	\N	\N	\N	\N	\N	\N	\N	\N	\N	f	\N	2025-08-30 07:27:56+00	2026-04-23 01:39:39.818334+00	0.5000	hours
135	pinealon	24	Glu–Asp–Arg	EDR	EDR is a neuroprotective tripeptide also studied by Khavinson’s group. It’s implicated in preventing neurodegenerative progression and supporting neuronal function, particularly in Alzheimer’s disease models	Epitalon binds to histones and/or RNA, modulates MAPK/ERK signaling, and influences transcription factors (e.g., PPARA, PPARG) as well as apoptotic and antioxidative proteins (e.g., caspase‑3, p53, SOD2, GPX1). It provides a stabilizing effect against homocysteine-induced neurotoxicity by modulating ERK activation timing and reducing ROS-mediated damage. In Alzheimer’s mouse models (5xFAD), Pinealon and Vesugen preserve dendritic spine integrity and enhance neuroplasticity; docking studies suggest specific promoter-level epigenetic effects.	https://www.corepeptides.com/wp-content/uploads/2024/09/Pinealon-Peptide-Structure.jpg	(4S)-4-Amino-5-[[(2S)-3-carboxy-1-[[(1S)-1-carboxy-4-(diaminomethylideneamino)butyl]amino]-1-oxopropan-2-yl]amino]-5-oxopentanoic acid	418.407 g/mol	\N	Neurodegeneration, Neuroplasticity, Oxidative Stress, Athletic Performance, Metabolic Health, Cell Survival	C15H26N6O8	Pinealon	\N	\N	\N	\N	\N	\N	\N	\N	\N	\N	\N	\N	\N	\N	\N	\N	\N	f	\N	2025-08-30 08:04:59+00	2026-04-23 01:39:39.818334+00	1.0000	hours
136	vesugen	24	Lys–Glu–Asp	Lysyl‑glutamyl‑aspartic acid, SCHEMBL3767701, Vitalis	Vesugen is a synthetic bioregulatory tripeptide also studied by Khavinson’s group. Primarily focused on vascular rejuvenation and systemic geroprotection.	Vesugen binds to gene promoter regions, influencing the expression of proteins such as Ki‑67 , SIRT1, endothelin‑1, connexins, VEGF, and p53, which play pivotal roles in vascular repair and aging. It enhances endothelial function, promoting NO-dependent vasorelaxation, improved extracellular matrix integrity, blood vessel elasticity, and red blood cell membrane stability. It suppresses SASP  markers like p16, p21, reduces telomeric damage, reduces endothelin‑1, increases SIRT1, improves mitochondrial function, and protects telomeric stability in endothelial cells. Vesugen supports synaptic plasticity and neuronal structures in Alzheimer's models preserving dendritic spines, enhancing long-term potentiation, and promoting stem cell differentiation.	https://pubchem.ncbi.nlm.nih.gov/image/imgsrv.fcgi?cid=87571363&t=l	(2S)-2‑amino‑butanoyl]amino]butanedioic acid (a structuring reflecting a Lys–Glu–Asp peptide)	390.39 g/mol	\N	Endothelial Dysfunction, Anti-Aging, Metabolic Disorder, Cognition, Injury Regenerative, Immunology	C15H26N4O8	Vesugen	\N	\N	\N	\N	\N	\N	\N	\N	\N	\N	\N	\N	\N	\N	\N	\N	\N	f	\N	2025-08-30 09:54:19+00	2026-04-23 01:39:39.818334+00	\N	\N
137	cortexin	21	\N	neuropeptide complex, tissue-derived peptide preparation, Geropharm	Cortexin is a neuropeptide complex derived from the cerebral cortex of young animals (cattle/pigs) under 12 months old. It represents a highly purified fraction of peptides—predominantly acidic and neutral—with an isoelectric point ranging between pH 3.5–9.5 and molecular weights of 1,000–10,000 Da. his preparation is used in clinical settings within Russia and some post‑Soviet countries as a neuroprotective and neurometabolic agent, employed in cases ranging from stroke and brain injury to developmental and cognitive disorders in both pediatric and adult patients.	Cortexin binds to key glutamatergic and GABAergic receptors, including: AMPA receptors, Kainate receptors, mGluR1, GABA_A1, mGluR5. Cortexin inhibits caspase-8, a key enzyme in the initiation of apoptosis. It shows lower or no activity against other proteases like caspase-1, -3, -9, cathepsin B, or calpain. This inhibition contributes to its neuroprotective effect in models of excitotoxicity. ortexin modulates the balance of excitatory/inhibitory neurotransmitters: enhancing GABA and serotonin, modulating dopamine release, and restoring neurochemical homeostasis. It also exerts antioxidant and anti-apoptotic protection, reducing lipid peroxidation and oxidative stress. It demonstrated ability to stimulate axonal and dendritic outgrowth, influence expression of neurotrophic factors, and support neural repair and plasticity.	\N	\N	1,000–10,000 g/mol	\N	Brain Ischemia, Cognitive Disorders, Behavioral Disorders, Epilepsy, Ototoxicity Protection, Neuroplasticity, Neuroprotection,	\N	Cortexin	\N	\N	\N	\N	\N	\N	\N	\N	\N	\N	\N	\N	\N	\N	\N	\N	\N	f	\N	2025-08-30 12:56:47+00	2026-04-23 01:39:39.818334+00	\N	\N
138	thymalin	24	Pyr-Ala-Lys-Ser-Gln-Gly-Gly-Ser-Asn	\N	Thymalin is a synthetic peptide derived from thymulin, a small peptide hormone originally extracted from the thymus gland in 1977. It is primarily investigated for immune modulation, anti-aging, and regenerative medicine applications.	Thymalin's mechanism is extremely multifaceted. It enhances T‑cell differentiation, activates natural killer cells, promotes balanced cytokine production, and helps restore immune balance. It supports protein synthesis, tissue healing, reduces systemic inflammation, and stabilizes homeostasis. It may affect the hypothalamic-pituitary-adrenal axis, modulate circadian-related immune decline, and influence astrocyte function in the CNS. Thymalin has demonstrated anti-aging potential. It enhances treatment outcomes in cancer, tuberculosis, psoriasis, chronic kidney inflammation, and cardiovascular diseases by improving immune surveillance and cellular function.	\N	\N	858.9 g/mol	\N	Immune Support, Anti-aging, Cancer Adjuvant, Cardiovascular Health, Infections, Neuroprotection, Circadian Rhythm	C33H54N12O15	Thymalin	\N	\N	\N	\N	\N	\N	\N	\N	\N	\N	\N	\N	\N	\N	\N	\N	\N	f	\N	2025-08-31 21:42:07+00	2026-04-23 01:39:39.818334+00	\N	\N
139	vilon	24	Lys–Glu	Lysylglutamate, Normophthal, Lys-glutamic acid	Vilon is a synthetic dipeptide, the shortest peptide recognized for biological activity. It’s considered a bioregulator due to its role in modulating immune function, tissue repair, anti-aging, and gene expression. It was developed based on analyses of thymus tissue extracts similiar to Thymalin.	Vilon reportedly interacts with chromatin, loosening tightly packed DNA similiar to HDAC inhibitors and reactivating transcription of genes crucial for cellular repair and protein synthesis. It stimulates immune cell activity, including T-lymphocytes and thymocytes, enhancing receptor expression on T/B cells, increasing cytokines like interleukins and interferons, and boosting argyrophilic nucleolar protein synthesis. Additional effects include increasing antithrombin III and protein C, enhancing fibrinolysis, improving vascular and metabolic homeostasis, and supporting organ-specific gene expression.	https://www.peptidesciences.com/media/wysiwyg/Vilon_Structure.png	2-(2,6-Diaminohexanoylamino)pentanedioic acid	257.30 g/mol	\N	Immune System, Tissue Regeneration, Anti-Aging, Longevity, Cardiovascular, Neurological Disease, Cancer, Metabolism, Resilience	C11H21N3O5	Vilon	\N	\N	\N	\N	\N	\N	\N	\N	\N	\N	\N	\N	\N	\N	\N	\N	\N	f	\N	2025-09-01 01:31:39+00	2026-04-23 01:39:39.818334+00	\N	\N
140	livagen	24	H‑Lys‑Glu‑Asp‑Ala‑OH	\N	Livagen is a synthetic tetrapeptide composed of four amino acids which has been shown to restore protein synthesis in aging cells and has also been shown to inhibit enkephalin degradation.	Livagen appears to decondense chromatin similiar to HDAC inhibitors, thereby reactivating silenced genes, especially ribosomal genes, which enhances protein synthesis, particularly in aged cells. It also inhibits enkephalin-degrading enzymes, raising levels of the body’s own opioid peptides. By modulating enkephalin levels, it may enhance mucosal protection, alter nitric oxide and prostaglandin signaling, and increase vagal nerve activation. Is also proposed to support DNA repair, telomerase activity, oxidative stress reduction, and neuroprotection.	https://peptidescalculator.com/assets/Livagen1-Dx7iYLFc.png	\N	461.5 g/mol	\N	Anti-Aging, Rejuvenation, Immune System, Pain, Mental Health, Neuroprotection, Injury Recovery	C18H31N5O9	Livagen	\N	\N	\N	\N	\N	\N	\N	\N	\N	\N	\N	\N	\N	\N	\N	\N	\N	f	\N	2025-09-01 02:27:41+00	2026-04-23 01:39:39.818334+00	\N	\N
141	cartalax	24	Ala–Glu–Asp	AED, T‑31, Alanyl‑glutamyl‑aspartic acid	Cartalax is a synthetic tripeptide bioregulator originating from the Russian peptide regimens developed at the St. Petersburg Institute of Bioregulation and Gerontology by Professor Vladimir Khavinson. It shows promise in supporting connective and cartilage tissue health.	Cartalax boosts cell proliferation, reduces apoptosis via p53 downregulation and improves fibroblast function across tissues like skin, cartilage, and kidneys. It inhibits MMP‑9, an enzyme that accelerates tissue breakdown during aging, and balances other MMPs (like MMP‑1) to harmonize tissue remodeling. Cartalax appears to influence gene networks related to aging markers such as IGF1, FOXO1, TERT, TNKS2, and NF‑κB, inducing changes ranging from 1.6- to 5.6-fold in tissues such as bone marrow stem cells. It may support cartilage and bone health by promoting extracellular matrix integrity and reducing inflammation. In renal models, Cartalax increases proliferation markers, decreases aging markers like p16, p21, and p53, and enhances SIRT‑6 expression, supporting longevity at the cellular level.	https://pubchem.ncbi.nlm.nih.gov/image/imgsrv.fcgi?cid=87815447&t=l	(2S)-2-[[(2S)-2-[[(2S)-2-aminopropanoyl]amino]-4-carboxybutanoyl]amino]butanedioic acid	333.29 g/mol	\N	Arthritis, Anti-Aging, Kidney Health, Tissue Remodeling	C12H19N3O8	Cartalax	\N	\N	\N	\N	\N	\N	\N	\N	\N	\N	\N	\N	\N	\N	\N	\N	\N	f	\N	2025-09-01 23:31:28+00	2026-04-23 01:39:39.818334+00	\N	\N
142	endoluten	24	\N	A‑8 pineal peptide bioregulator	Endoluten is a natural peptide complex derived from the pineal gland of young animals, commonly calves up to 12 months old. It was developed within the framework of Russian peptide bioregulator research, notably by Professor Vladimir Khavinson and colleagues.	Endoluten targets pineal gland and neuroendocrine cells to help normalize melatonin production, thereby adjusting circadian rhythms and systemic hormonal balance. It reportedly influences protein synthesis, telomere maintenance, and cellular division capacity, contributing to anti-aging effects in cellular models. The peptide complex exhibits antioxidant properties, helps regulate metabolic processes within neuroendocrine tissues, and supports adaptation to stress or extreme conditions. In studies involving patients post-radiation or chemotherapy, Endoluten improved leukocyte and lymphocyte counts, enhancing immune function and aiding recovery	\N	\N	\N	\N	Neuroendocrine Modulation, Anti-Anging, Adaptation Support, Immune System	\N	Endoluten	\N	\N	\N	\N	\N	\N	\N	\N	\N	\N	\N	\N	\N	\N	\N	\N	\N	f	\N	2025-09-01 23:51:12+00	2026-04-23 01:39:39.818334+00	\N	\N
143	prostatilen	24	\N	Bovine prostate peptide extract	Prostatilen is a bioregulatory peptide complex derived from the prostate gland tissue of bulls. It belongs to a class of organ-specific peptide extracts and was first developed in the 1980s in Russia.	As a low-molecular-weight peptide extract, Prostatilen can penetrate cells and the nucleus, interacting with gene promoter regions. This interaction modulates gene expression, promoting transcription and protein synthesis for functional restoration. It enhances synthesis of anti-histamine and anti-serotonin antibodies and inhibits MCP‑1-driven immune cell migration, reducing inflammation and Stimulates T‑lymphocytes, NK cells, and phagocytosis. In prostate and bladder it reduces platelet aggregation and coagulation, increases fibrinolytic activity, enhances microvascular blood flow, and modulates the detrusor muscle in a context-dependent manner, enhancing activity when low and suppressing when hyperactive, therefore restoring normal bladder function. It also Stimulates regeneration in aging prostate cell cultures, counteracting degeneration and age-related involutional changes. Other than that it also seems to lower lipids and enhance monoamines.	\N	\N	\N	\N	Prostate Disease, Urinary Tract Disease, Infertility, Urinary Disorders	\N	Prostatilen	\N	\N	\N	\N	\N	\N	\N	\N	\N	\N	\N	\N	\N	\N	\N	\N	\N	f	\N	2025-09-02 02:17:39+00	2026-04-23 01:39:39.818334+00	\N	\N
144	retinalamin	24	\N	cattle retinal polypeptides	Retinalamin is a peptide bioregulator derived from bovine retinal tissue, created by the St. Petersburg Institute of Bioregulation and Gerontology and formulated as a complex of water‑soluble polypeptide fragments.	Retinalamin enhances metabolic processes in retinal tissues, normalizes cellular membrane function, and boosts intracellular protein synthesis. It regulates lipid peroxide oxidation, prevents glutamate-induced excitotoxicity, and optimizes Müller glia activity all of which contribute to cell protection against oxidative stress. Retanalamin  promotes retinal repair and protection by promoting interaction between the retinal pigment epithelium and photoreceptors, reducing local inflammation, normalizing vascular permeability, and stimulating regeneration of retinal neurons. It also seems to improve ocular blood flow and support energy metabolism in retinal tissues	\N	\N	\N	\N	Retinal Damage, Optic Nerve Damage, Retinal Dystrophy	\N	Retinalamin	\N	\N	\N	\N	\N	\N	\N	\N	\N	\N	\N	\N	\N	\N	\N	\N	\N	f	\N	2025-09-02 02:44:23+00	2026-04-23 01:39:39.818334+00	\N	\N
145	crystagen	24	Pro-Glu-Asp	AC‑6 peptide complex, prolyl-glutamyl-aspartic acid	Crystagen®  is a short synthetic peptide designed as an immune system bioregulator by the St. Petersburg's Institute of Bioregulation intended for age-related immune decline.	Crystagen enhances T-lymphocyte activity, modulates CD3+, CD4+/CD8+ ratios, and activates B-cell function, particularly in aged or immunocompromised models. Has demonstrated geroprotective effects, maintaining thymic cortex-medulla structure and increasing proliferation markers. Has been demonstrated to improve stress resilience, HSP gene expression, and reduced respiratory infection rates.	https://pubchem.ncbi.nlm.nih.gov/image/imgsrv.fcgi?cid=145457458&t=s	(2S)-2-[[(2S)-4-carboxy-2-[[(2S)-pyrrolidine-2-carbonyl]amino]butanoyl]amino]butanedioic acid	359.34 g/mol	\N	Immune System, Thymus Regeneration, Stress, Infection	C14H21N3O8	Crystagen	\N	\N	\N	\N	\N	\N	\N	\N	\N	\N	\N	\N	\N	\N	\N	\N	\N	f	\N	2025-09-02 03:25:55+00	2026-04-23 01:39:39.818334+00	\N	\N
146	sigumir	24	\N	Cartilage Peptide Bioregulator A‑4, Peptide complex A‑4	Sigumir is a natural peptide bioregulator complex derived from the cartilage and bone tissues of young animals, typically calves under 12 months old. The peptides are low molecular weight and extracted via patented ultrafiltration processes.	Sigumir’s peptides exhibit selective action on cartilage and bone cells, enhancing metabolism and cell trophism, therefore improving nourishment and maintenance of those tissues. By regulating metabolic processes in cartilage tissue, Sigumir helps normalize cartilage function, potentially slowing degenerative changes associated with aging. The peptide complex may promote chondrocyte activity and extracellular matrix synthesis, enhancing joint flexibility, bone density, and recovery from degeneration. It may modulate inflammatory responses in joint tissue, leading to reduced pain perception and improved range of motion.	\N	\N	\N	\N	Inflammation, Pain Management, Arthritis, Flexibility, Bone Density,	\N	Sigumir	\N	\N	\N	\N	\N	\N	\N	\N	\N	\N	\N	\N	\N	\N	\N	\N	\N	f	\N	2025-09-02 16:29:43+00	2026-04-23 01:39:39.818334+00	\N	\N
147	ventfort	24	\N	blood vessel peptide bioregulator, Cytomaxes A‑3 complex	Ventfort, also referred to as a blood vessel peptide bioregulator, is a natural peptide complex derived from the aortic tissues of young animals, typically calves under 12 months old. It belongs to the Cytomaxes class of bioregulators -  tissue-derived peptide extracts aimed at nourishing their corresponding human tissues. Vesugen is the synthetic tripeptide active core.	Ventfort’s peptides are preferentially taken up by vascular wall cells to improve cell trophism, normalize metabolism, and restore functional and morphological integrity of vessel walls. It has been demonstrated to improve lipids and atherosclerosis. Has displayed epigenetic regulation of vascular genes: downregulation of endothelin-1, upregulation of SIRT1, normalization of connexin expression, and modulation of Ki-67, p53, and E‑selectin for enhanced cell renewal and inhibition of atherosclerotic plaque formation. Interestingly studies suggest it may support neurovascular health by stimulating serotonin synthesis in aging cortical cells and partially restoring dendritic spine density under amyloid-induced stress.	\N	\N	\N	\N	Angio‑protection, Atherosclerosis, Hyperlipidemia, Endothelial Dysfunction, Neurodegenerative DIsease	\N	Ventfort	\N	\N	\N	\N	\N	\N	\N	\N	\N	\N	\N	\N	\N	\N	\N	\N	\N	f	\N	2025-09-02 17:51:21+00	2026-04-23 01:39:39.818334+00	\N	\N
148	bronchogen	24	Ala‑Glu‑Asp‑Leu	AEDL, Bronchial peptide bioregulator	Bronchogen is a synthetic tetrapeptide bioregulator, derived from the work led by Vladimir Khavinson  at the St. Petersburg Institute of Bioregulation. Bronchogen is designed to regulate lung tissue health, in particular the bronchial epithelium.	Bronchogen increases DNA melting temperature by ~3 °C in in vitro assays, indicating it reinforces genetic stability. It preferentially binds to certain DNA sequences, potentially influencing methylation sites and gene expression via epigenetic pathways. It regulates critical lung-development genes essential for bronchial epithelial function and differentiation. It promotes bronchial epithelium regeneration and protection by increasing surfactant production and modulating inflammatory cytokines. Lastly it supports airway barrier maintenance and immunoregulation.	https://www.peptidesciences.com/media/wysiwyg/Bronchogen_Molecule.png	Ala‑Glu‑Asp‑Leu	446.45 g/mol	\N	Respiratory Health, Age-related Respiratory Decline, DNA Integrity	C18H30N4O9	Bronchogen	\N	\N	\N	\N	\N	\N	\N	\N	\N	\N	\N	\N	\N	\N	\N	\N	\N	f	\N	2025-09-02 18:42:49+00	2026-04-23 01:39:39.818334+00	\N	\N
149	pancragen	24	Lys–Glu–Asp–Trp	KEDW	Pancragen is a synthetic tetrapeptide bioregulator, a structural analog of a naturally occurring peptide extracted from pancreatic tissues of young animals. Developed through Russian bioregulator research under the guidance of Professor Vladimir Khavinson and colleagues at the St. Petersburg Institute of Bioregulation, Pancragen is aimed at preserving pancreatic function as part of anti-aging strategies.	Pancragen penetrates cell membranes and interacts with nuclear or epigenetic machinery, promoting transcription of pancreatic differentiation. It upregulates anti-apoptopic pathways like MMP-2, MMP-9, CD79α, Mcl-1 and proliferative markers like PCNA, Ki-67. It downregulates pro-apoptopic pathway p53. It also affects other aging markers like caspase-3, cathepsin B, TNF-α and IGF-1. It modulates epigenetics by altering DNA methylation in promoter regions of PDX1, PAX6, NGN3, restoring gene expression profiles closer to a younger individual's, in pancreatic cells. Additionally it improves glucose homeostasis by lowering fasting glucose and insulin and enhancing insulin sensitivity and endothelial function, including improved adhesive properties in hyperglycemic models.	https://www.peptidesciences.com/media/wysiwyg/Pancragen_Molecule.png	Lys–Glu–Asp–Trp	576.25 g/mol	\N	Insulin Resistance, Anti-Aging, Pancreatic Health, Epigenetic Modulation, Vascular Health, Metabolic Health	C26H36N6O9	Pancragen	\N	\N	\N	\N	\N	\N	\N	\N	\N	\N	\N	\N	\N	\N	\N	\N	\N	f	\N	2025-09-02 20:07:47+00	2026-04-23 01:39:39.818334+00	\N	\N
150	testoluten	24	\N	peptide complex A‑13, Testes Peptide Bioregulator A‑13	Testoluten is a natural peptide bioregulator complex derived from the testicular tissue of young animals. It contains the peptide complex A‑13, a collection of low-molecular-weight peptides designed to support testicular function and overall male reproductive health. Long-term usage in animal models has reportedly increased average lifespan by 20–40%, while in human applications, widespread physiological improvements and reduced mortality over 6–12 years have been observed.	Testoluten’s peptides target testicular cells, supporting their metabolic function and vitality. It regulates cellular metabolism and gene expression to enhance protein synthesis in testicular cells, restores hormones production, enhances spermatogenesis and sperm motility.	\N	\N	\N	\N	Sexual Health, Fertility, Hypogonadism, Testicular Hypofunction	\N	Testoluten	\N	\N	\N	\N	\N	\N	\N	\N	\N	\N	\N	\N	\N	\N	\N	\N	\N	f	\N	2025-09-02 23:35:47+00	2026-04-23 01:39:39.818334+00	\N	\N
151	chonluten	24	Glu‑Asp‑Gly	EDG tripeptide, T‑34 tripeptide, Glutamyl‑aspartyl‑glycine, EDG	Chonluten is a short, synthetic peptide originally derived from lung or bronchial tissues. Developed by researchers at the Saint Petersburg Institute of Bioregulation and Gerontology, led by Dr. Vladimir Khavinson, Chonluten was identified among short peptides with the potential for organ-specific regeneration and immune modulation, especially targeting the respiratory system.	Chonluten is thought to penetrate nuclei and interact with DNA or chromatin, influencing gene expression via transcriptional or epigenetic mechanisms. Chonluten is suggested to module expression of c-Fos, HSP70, SOD, COX-2, TNF‑α and others. Chonluten suppresses inflammatory cytokine production like IL-6, TNF‑α and IL-17. It supports mucosal barrier restoration in bronchial epithelium and stabilizes mucosal integrity and accelerates repair in GI tissues.	https://pubchem.ncbi.nlm.nih.gov/image/imgsrv.fcgi?cid=194641&t=s	(4S)-4-amino-5-[[(2S)-3-carboxy-1-(carboxymethylamino)-1-oxopropan-2-yl]amino]-5-oxopentanoic acid	319.27 g/mol	\N	Respiratory Health, Post-infection Recovery, Gastrointestinal Tract Repair, Anti-Aging	C11H17N3O8	Chonluten	\N	\N	\N	\N	\N	\N	\N	\N	\N	\N	\N	\N	\N	\N	\N	\N	\N	f	\N	2025-09-03 00:05:09+00	2026-04-23 01:39:39.818334+00	\N	\N
152	thyreogen	24	\N	Complex A‑2, Thyroid Peptide Bioregulator A‑2, Cytomaxes A‑2 complex	Thyreogen is a natural peptide bioregulator complex composed of thyroid tissue-derived peptides harvested from the thyroid glands of young animals. It is designed to normalize thyroid gland metabolism and function, acting effectively in both hypo- and hyperthyroidism scenarios.	Thyreogen is composed of short signaling peptides that penetrate thyroid cell nuclei and bind to specific DNA promoter sequences, activating RNA polymerase and initiating gene transcription - essentially restoring normal metabolic function in thyroid cells. Interestingly it exhibits a bidirectional regulatory effect of upregulating thyroid function if its hypoactive and downregulating it if its hyperactive. Lastly it supports tissue regeneration through epigenetic and gene expression mechanisms, promoting a balanced thyroid state.	\N	\N	\N	\N	Metabolic Health, Thyroid Dysfunction, Age-related Thyroid Decline, Endocrine Balance	\N	Thyreogen	\N	\N	\N	\N	\N	\N	\N	\N	\N	\N	\N	\N	\N	\N	\N	\N	\N	f	\N	2025-09-03 02:29:50+00	2026-04-23 01:39:39.818334+00	\N	\N
159	zhenoluten	24	\N	ZhENOLUTEN, Genoluten, Genaluten	Zhenoluten is a bioregulatory peptide complex derived from ovarian tissue of young animals. It belongs to a class of organ-specific peptide extracts and was first developed in the 1980s in Russia.	Zhenoluten is believed to act as a regulatory signal, interacting with DNA promoter sequences to initiate protein synthesis in ovarian cells through RNA polymerase activation. Zhenoluten:  Normalizes cellular metabolism in ovarian tissue, promotes oocyte maturation, restore cyclic ovarian activity, supports hormonal regulation.	\N	\N	\N	\N	Fertility, Endocrinology, Hormonal Regulation	\N	Zhenoluten	\N	\N	\N	\N	\N	\N	\N	\N	\N	\N	\N	\N	\N	\N	\N	\N	\N	f	\N	2025-09-09 16:12:02+00	2026-04-23 01:39:39.818334+00	\N	\N
160	visoluten	24	\N	A‑11	Visoluten is a peptide bioregulator or more specifically A‑11 eye tissue peptide complex - extracted from the eye tissues of young animals. It was developed by researchers at the St. Petersburg Institute of Bioregulation and Gerontology	Visoluten mechanism hinges on the idea of short signaling peptides acting as gene expression regulators. It binds to specific promoter regions in the DNA of corresponding tissue, causes local unwinding of the DNA helix and facilitates RNA polymerase binding and activation, thereby stimulating synthesis of proteins essential for tissue function and repair.	\N	\N	\N	\N	Ophthalmology, Neurology, Gerontology, Regenerative Therapy	\N	Visoluten	\N	\N	\N	\N	\N	\N	\N	\N	\N	\N	\N	\N	\N	\N	\N	\N	\N	f	\N	2025-09-10 05:06:37+00	2026-04-23 01:39:39.818334+00	\N	\N
161	vesselget	24	\N	A-7 vascular peptide complex, Cytomax A-7	Vesselget is a peptide complex isolated from the vascular tissue of young calves. It is part of the Cytomax line of peptide bioregulators developed by the St. Petersburg Institute of Bioregulation and Gerontology.	Vesselget translocates into the cell nucleus of endothelial and smooth muscle cells and there it interact with specific DNA sequences, modulating chromatin conformation, thereby activating transcription of vascular-specific genes. This regulation improves synthesis of structural and regulatory proteins necessary for vascular wall stability. Vesselget peptides enhance endothelial nitric oxide synthase expression - promoting vasodilation, reduce endothelial dysfunction - a key factor in hypertension and atherosclerosis, Normalize barrier function - reducing vascular permeability and inflammatory infiltration. Vesselget peptides help maintain epigenetic stability in vascular cells by supporting DNA repair and chromatin structure, modulating histone acetylation/methylation, regulating microRNAs linked to vascular inflammation and remodeling.	\N	\N	\N	\N	Cardiovascular Health, Epigenetics, Endothelial Dysfunction, Genetic Transcription	\N	Vesselget	\N	\N	\N	\N	\N	\N	\N	\N	\N	\N	\N	\N	\N	\N	\N	\N	\N	f	\N	2025-09-11 16:25:14+00	2026-04-23 01:39:39.818334+00	\N	\N
163	taxorest	24	\N	Bronchial peptide complex, bronchoprotector peptide	Taxorest is a peptide bioregulator complex developed from bronchial mucosa extracts. It belongs to the family of short peptides studied by Vladimir Khavinson and colleagues at the St. Petersburg Institute of Bioregulation and Gerontology.	Taxorest peptides bind selectively to DNA in bronchial epithelial and immune cells and there it modulates mucosal repair proteins, antioxidant enzymes, cytokines. Taxorest promotes differentiation of progenitor cells into functional ciliated epithelial cells - improving airway clearance, enhances synthesis of glycoproteins and surfactant-related proteins - restoring normal mucus viscosity, stimulates fibroblast activity for balanced connective tissue turnover. It normalizes the ratio of Th1/Th2 lymphocytes, reducing allergic-type hyperreactivity, enhances macrophage phagocytosis and local antigen presentation and improves production of secretory IgA - strengthening mucosal barrier immunity. Taxorest also downregulates excessive NF-κB signaling and  lowers neutrophil recruitment and oxidative stress in bronchial mucosa.	\N	\N	\N	\N	COPD, Pulmonary decline, Asthma, Bronchitis	\N	Taxorest	\N	\N	\N	\N	\N	\N	\N	\N	\N	\N	\N	\N	\N	\N	\N	\N	\N	f	\N	2025-09-11 17:25:06+00	2026-04-23 01:39:39.818334+00	\N	\N
164	svetinorm	24	\N	Liver peptide bioregulator A-7, Natural liver peptides, Peptide complex A-7	Svetinorm is a bioregulatory liver peptide complex derived from the liver tissue of young animals. It belongs to a class of organ-specific peptide extracts and was first developed in the 1980s in Russia.	Svetinorm is believed to act as a regulatory signal, interacting with DNA promoter sequences to initiate protein synthesis in hepatocytes through RNA polymerase activation.\r\nIt normalizes cellular metabolism in liver tissue, promotes regeneration of hepatocytes, supports lipid metabolism, enhances detoxification processes, and contributes to restoration of liver function after damage.	\N	\N	\N	\N	Hepatology, Chronic Hepatitis, Intoxication Recovery, Lipid Metabolism Disorders, Digestive Health, Anti-aging Support	\N	Svetinorm	\N	\N	\N	\N	\N	\N	\N	\N	\N	\N	\N	\N	\N	\N	\N	\N	\N	f	\N	2025-09-17 01:31:25+00	2026-04-23 01:39:39.818334+00	\N	\N
165	ovagen	24	Glu‑Asp‑Leu	\N	Ovagen is a synthetic tripeptide described to have effects particularly in the liver and gastrointestinal tract: modulating fibrosis, protecting mucosal layers, counteracting damage from antibiotics, toxins, chemotherapy.	Ovagen acts as a competitive inhibitor of the mature HIV‑1 protease enzyme. It is derived from a region of the Gag‑Pol polyprotein of HIV‑1.  Studies have shown Ovagen to have promise as a potential anti-aging peptide in the liver and GI tract. Research has shown that Ovagen can reduce fibrosis in the liver and protect the GI mucosal layer.	\N	(2S)‑2‑(4‑carboxy‑3‑oxobutanamido)‑4‑oxo‑4‑((2S)‑4‑methylpentanoylamino)butanoic acid	375.37 g/mol	\N	HIV, Immunology, Hepatology, Gastroenterology, Anti-Aging	C15H25N3O8	Ovagen	\N	\N	\N	\N	\N	\N	\N	\N	\N	\N	\N	\N	\N	\N	\N	\N	\N	f	\N	2025-09-20 23:12:05+00	2026-04-23 01:39:39.818334+00	\N	\N
166	stamakort	24	\N	Peptide Complex A‑10	Stamakort is a bioregulator peptide complex derived from gastric mucosa of young, healthy animals.	Stamakort increases protein synthesis in gastric musocal cells, helps restore damaged mucosal lining and improves gastric function like acid and enzyme secretion.	\N	\N	\N	\N	Gastritis, Gastroduodenitis, Ulcers, Pancreatitis, Malnutrition, Digestive Dysfunction	\N	Stamakort	\N	\N	\N	\N	\N	\N	\N	\N	\N	\N	\N	\N	\N	\N	\N	\N	\N	f	\N	2025-09-20 23:28:59+00	2026-04-23 01:39:39.818334+00	\N	\N
167	pielotax	24	\N	peptide complex A‑9	Pielotax is a peptide bioregulator developed by the Russian Scientific-Production Center of Revitalization and Health. It is derived from the renal parenchyma of young animals, specifically designed to support kidney function. The concept of peptide bioregulators was pioneered by Professor Vladimir Khavinson, who discovered that short peptides could selectively interact with DNA to regulate gene expression, thereby restoring cellular function and promoting tissue regeneration.	Pielotax selectively targets kidney cells. It binds to specific DNA sequences within the promoter regions of genes in kidney cells. This binding induces the unwinding of the DNA double helix, facilitating the activation of RNA polymerase and initiating gene transcription. The result is the upregulation of protein synthesis, which supports cellular repair, regeneration, and the restoration of normal metabolic functions within the kidneys.	\N	\N	\N	\N	Nephropathy, Kidney Stones, Renal Failure, Nephroptosis	\N	Pielotax	\N	\N	\N	\N	\N	\N	\N	\N	\N	\N	\N	\N	\N	\N	\N	\N	\N	f	\N	2025-09-20 23:41:48+00	2026-04-23 01:39:39.818334+00	\N	\N
168	gotratix	24	\N	Muscle Peptide Bioregulator A‑18, peptide complex A‑18	Gotratix is a peptide complex produced by the St. Petersburg Institute of Bioregulation and Gerontology. It is a natural peptide extract from animal muscle tissue of young animals.	Gotratix's peptide fractions are said to be information molecules that interact with promoter regions of certain genes, causing disjoining of DNA double helix strands and activation of RNA polymerase, thereby inducing protein synthesis. These peptides are claimed to have a selective effect on myocytes, normalizing metabolism in these cells, increasing their functional activity, and reducing muscle fatigue under physical stress. It is believed to regulate peroxidation processes in muscle tissues.	\N	\N	\N	\N	Performance Enhancement, Chronic Fatigue, Atrophy Prevention, Anti-Aging	\N	Gotratix	\N	\N	\N	\N	\N	\N	\N	\N	\N	\N	\N	\N	\N	\N	\N	\N	\N	f	\N	2025-09-20 23:47:08+00	2026-04-23 01:39:39.818334+00	\N	\N
169	glandokort	24	\N	peptide complex A‑17	Glandokort is a peptide complex produced by the St. Petersburg Institute of Bioregulation and Gerontology. It is a natural peptide extract derived from adrenal gland tissue of young animals.	Glandokort's peptides normalize metabolism, promote protein synthesis in adrenal cells and help restore functional activity of the gland in conditions of stress or aging.	\N	\N	\N	\N	Fatigue, Adrenal Fatigue, Stress, Endocrinology	\N	Glandokort	\N	\N	\N	\N	\N	\N	\N	\N	\N	\N	\N	\N	\N	\N	\N	\N	\N	f	\N	2025-09-20 23:56:26+00	2026-04-23 01:39:39.818334+00	\N	\N
170	chelohart	24	\N	peptide complex A‑14, bioregulator of cardiac muscle peptides	Chelohart is a peptide complex produced by the St. Petersburg Institute of Bioregulation and Gerontology. It is a natural peptide extract derived from the heart tissue of young animals.	Chelohart peptides act selectively on cardiac muscle cells. It is believed to help normalize metabolic processes in heart muscle cells by improving protein synthesis, protein turnover and restoring optimal functioning of cardiomyocytes. It is also used for reducing or preventing atrophic or degenerative changes in heart muscle.	\N	\N	\N	\N	Myocardial Function, Cardiovascular Disease, Cardiac Insufficiency, Ischemic Heart Disease	\N	Chelohart	\N	\N	\N	\N	\N	\N	\N	\N	\N	\N	\N	\N	\N	\N	\N	\N	\N	f	\N	2025-09-21 00:04:48+00	2026-04-23 01:39:39.818334+00	\N	\N
155	hgh-fragment-176-191	19	Tyr‑Leu‑Arg‑Ile‑Val‑Gln‑Cys‑Arg‑Ser‑Val‑Glu‑Gly‑Ser‑Cys‑Gly‑Phe	\N	HGH Fragment 176‑191 is a synthetic peptide derived from the C‑terminal region of human growth hormone, specifically amino acids 176–191.	Fragment 176‑191 appears to activate fat-cell pathways promoting lipolysis, while simultaneously inhibiting lipogenesis. The fragment may enhance beta‑3 adrenergic receptor expression in adipose tissue, increasing fat burning in fat cells and possibly skeletal muscle thermogenesis, without broadly triggering growth pathways. Unlike full-length growth hormone, it appears not to increase IGF‑1 levels or affect insulin resistance, making its effects more adipose-specific.	https://upload.wikimedia.org/wikipedia/commons/thumb/c/c9/Human_Growth_Hormone_Fragment_176-191.svg/330px-Human_Growth_Hormone_Fragment_176-191.svg.png	H-Phe-Leu-Arg-Ile-Val-Gln-Cys(1)-Arg-Ser-Val-Glu-Gly-Ser-Cys(1)-Gly-Phe-OH	1815 g/mol	\N	Obesity, Recomposition, Insulin Resistance	C78H125N23O23S2	HGH Fragment 176-191	\N	\N	\N	\N	\N	\N	\N	\N	\N	\N	\N	\N	\N	\N	\N	\N	\N	f	\N	2025-09-07 21:07:41+00	2026-04-23 01:39:39.818334+00	0.5000	hours
156	follistatin	28	MVRARHQPGGLCLLLLLLCQFMEDRSAQAGNCWLRQAKNGRCQVLYKTELSKEECCSTGR LSTSWTEEDVNDNTLFKWMIFNGGAPNCIPCKETCENVDCGPGKKCRMNKKNKPRCVCAP DCSNITWKGPVCGLDGKTYRNECALLKARCKEQPELEVQYQGRCKKTCRDVFCPGSSTCV VDQTNNAYCVTCNRICPEPASSEQYLCGNDGVTYSSACHLRKATCLLGRSIGLAYEGKCI KAKSCEDIQCT	FST, Activin-binding protein, FS‑344, FS‑315, FS‑288, FSP	Follistatin is a secreted glycoprotein that binds and antagonizes several members of the TGF‑β superfamily. Initially discovered as a factor that suppresses follicle-stimulating hormone secretion, it has a broader physiological role in regulating cell differentiation, embryogenesis, and tissue regeneration.	Follistatin binds and neutralizes activin, myostatin, and other TGF‑β ligands, preventing them from interacting with their receptors and propagating downstream signaling. By inhibiting myostatin, follistatin removes an inhibitory checkpoint on muscle hypertrophy and hyperplasia, enhancing muscle growth and regeneration. Follistatin suppresses FSH release by neutralizing activin in the pituitary, modulating reproductive hormone dynamics. It regulates BMP signaling, influencing bone formation, cartilage induction, and embryonic axis formation.	https://upload.wikimedia.org/wikipedia/commons/thumb/0/06/PDB_2b0u_EBI.jpg/250px-PDB_2b0u_EBI.jpg	\N	38,006.8 g/mol	\N	Tissue Regeneration, Muscle Growth, Endocrinology	38,006.8 g/mol	Follistatin	\N	\N	\N	\N	\N	\N	\N	\N	\N	\N	\N	\N	\N	\N	\N	\N	\N	f	\N	2025-09-07 21:25:50+00	2026-04-23 01:39:39.818334+00	18.0000	hours
157	vasoactive-intestinal-peptide	13	H‑His‑Ser‑Asp‑Ala‑Val‑Phe‑Thr‑Asp‑Asn‑Tyr‑Thr‑Arg‑Leu‑Arg‑Lys‑Gln‑Met‑Ala‑Val‑Lys‑Lys‑Tyr‑Leu‑Asn‑Ser‑Ile‑Leu‑Asn‑NH₂	VIP, Aviptadil, Vasoactive Intestinal Polypeptide, VIP acetate	VIP is a neuropeptide discovered in 1970 from porcine duodenum. It belongs to the secretin/glucagon peptide family and is widely produced in the gut, pancreas, central nervous system, heart, lungs, and immune cells.	VIP binds to GPCRs VPAC1 and VPAC2, activating adenylate cyclase, increasing intracellular cAMP, and triggering PKA-mediated signaling. It functions as a potent vasodilator, promotes smooth muscle relaxation, raises heart rate, enhances glycogenolysis, and reduces blood pressure. In immune cells, VIP suppresses pro-inflammatory pathways and promotes anti-inflammatory programs, including Treg induction and IL‑10 upregulation. VIP safeguards epithelial cells by improving mitochondrial energy production and attenuating oxidative/apoptotic injury during inflammation or radiation exposure. It also supports progenitor cell proliferation and secretory differentiation via p38 MAPK.	https://pubchem.ncbi.nlm.nih.gov/image/imgsrv.fcgi?cid=53314964&t=l	\N	3,325 g/mol	\N	Immunology, Epithelial Health, Neuroprotection, Endothelial Dysfunction	C147H238N44O42S	Vasoactive Intestinal Peptide	\N	\N	\N	\N	\N	\N	\N	\N	\N	\N	\N	\N	\N	\N	\N	\N	\N	f	\N	2025-09-07 22:54:56+00	2026-04-23 01:39:39.818334+00	3.0000	minutes
176	zinc-thymulin	3	H-Pyr-Ala-Lys-Ser-Gln-Gly-Gly-Ser-Asn-OH	Zn-Thymulin, Zinc thymic factor, Zinc facteur thymique serique	Zn-Thymulin is a metallopeptide conjugate of Zinc and Thymulin. Thymulin is a peptide produced by the thymus in relation with the circadian rhythm. It has significant immune and neuroendocrine effects. Its analgesic, neuroprotective and anti-inflammatory. Its deficiency is associated with Anorexia Nervosa. Zinc deficiency can simulate and induce Thymulin deficiency and a big portion of Zinc deficiency symptoms can be explained by lack of Thymulin. Thymulin's effects are zinc dependant which is why it is conjugated into a metallopeptide with Zinc.	Thymulin induces intra and extra-thymic T cell differentiation, stimulates T helper cells, regulates cytotoxic T lymphocytes. Additionally it also regulates cytokines especially IL-2. It's anti-inflammatory effects are mediated by Treg activity, Nf-kB regulation, M2 macrophage polarization, NK cell enhancement and cytokinen modulation. Zn-Thymulin mediated localized zinc delivery, anti-inflammatory effects and its effects on T-cells promote transition into the anagen phase and hair proliferation.	https://muscleandbrawn.com/wp-content/uploads/2023/05/ZN-Thymulin.png	L-Pyroglutamyl-L-alanyl-L-lysyl-L-seryl-L-glutaminyl-glycyl-glycyl-L-seryl-L-asparagine	858.864 g/mol	\N	\N	C33H54N12O15	Zinc Thymulin	\N	\N	\N	\N	\N	\N	\N	\N	\N	\N	\N	\N	\N	\N	\N	\N	\N	f	\N	2025-10-07 11:33:03+00	2026-04-23 01:39:39.818334+00	1.5000	hours
177	fgl	13	H-Glu-Val-Tyr-Val-Val-Ala-Glu-Asn-Gln-Gln-Gly-Lys-Ser-Lys-Ala-OH	HY-P3281, DA-53184, CS-0655069, NCAM-Mimetic	FGL is derived from neural cell adhesion molecule and has been extensively studied for its neurotrophic effect that include neuroprotection, cognitive enhancement, neurogenesis and neuroplasticity.	FGL activates FGFR1 which engages ERK, PI3K-Akt, PLCγ FRS2α, Shc pathways. This leads to increased expression of survival proteins via PI3K/Akt — promoting neuron survival under stress, enhanced growth/differentiation/neuro-structural changes: neurite outgrowth, synapse formation, enhanced insertion/delivery of AMPA receptors at synapses via MAPK/PKC/CaMKII pathways and modulation of neuroinflammation via up-regulation of neuronal CD200, increasing glial IL-4, reducing microglial activation and IL-1β.	\N	N-[(2S)-2-amino-3-phenylpropanoyl]-L-glycine	1649.8 g/mol	\N	Cognitive Enhancement, Neurodegenerative Disease, Neuronal Regeneration	C71H116N20O25	FGL	\N	\N	\N	\N	\N	\N	\N	\N	\N	\N	\N	\N	\N	\N	\N	\N	\N	f	\N	2025-10-07 12:33:11+00	2026-04-23 01:39:39.818334+00	1.5000	hours
205	snap-8	27	EMQRRAD	Acetyl octapeptide-3	SNAP-8 is a synthetic peptide aimed to provide a safer alternative to Botox.	SNAP-8 targets SNARE complex, same target as Botox, by competing with them. This leads to impaired release of acetylcholine and therefore decreased muscle contraction intensity. Due to the localized effect it only affects muscles responsible for fine wrinkles rather than facial movement. Unlike Botox it is non-invasive, doesn't risk Botulism and is dependant on consistent use therefore safer in case of adverse effects.	https://pubchem.ncbi.nlm.nih.gov/image/imgsrv.fcgi?cid=71587832&t=l	\N	1073.2 g/mol	\N	Anti-Aging, Skincare	C42H72N16O15S	SNAP-8	\N	\N	\N	\N	\N	\N	\N	\N	\N	\N	\N	\N	\N	\N	\N	\N	\N	f	\N	2025-12-14 17:58:11+00	2026-04-23 01:39:39.818334+00	0.5000	hours
206	kisspeptin-10	4	YNWNSFGLRF	Metastin 45-54, KP10	Kisspeptin-10 is a key neuropeptide involved in regulating the HPG axis, especially during development.	Kisspeptin-10, through binding to its Kiss1R receptor, it depolarizes and excites GnRH neurons leading to increased GnRH secretion. It is necessary during development where it acts as a catalyst for puberty onset. Additionally kisspeptin-10 is involved in tumor suppression by inducing CRSP3 gene, halting the tumor from spreading and growing. Lastly it increases secretion of aldosterone and insulin.	https://pubchem.ncbi.nlm.nih.gov/image/imgsrv.fcgi?cid=25240297&t=l	H-Tyr-Asn-Trp-Asn-Ser-Phe-Gly-Leu-Arg-Phe-NH2	1302.4 g/mol	\N	Cancer, Hypogonadism, Hormone Optimization, Puberty	C63H83N17O14	Kisspeptin-10	\N	\N	\N	\N	\N	\N	\N	\N	\N	\N	\N	\N	\N	\N	\N	\N	\N	f	\N	2025-12-14 18:18:49+00	2026-04-23 01:39:39.818334+00	4.0000	minutes
207	dnsp-11	13	PPEAPAEDRSL-NH2	Dopamine Neuron Stimulating Peptide-11, GDNF propeptide DNSP-11	DNSP-11 is a peptide derived from the proprotein region of Glial Cell Line-Derived Neurotrophic Factor. It was developed for Parkinson's Disease.	Unlike parent compound GDNF it does not signal through GRFa/RET, instead its been identified to work by increasing ERK1/2 phosphorylation and decreasing nuclear GADPH.	\N	Prolyl-prolyl-glutamyl-alanyl-prolyl-alanyl-glutamyl-aspartyl-arginyl-seryl-leucinamide	1180.27 g/mol	\N	Parkinson's Disease, Cognitive Support	C43H70N12O25	DNSP-11	\N	\N	\N	\N	\N	\N	\N	\N	\N	\N	\N	\N	\N	\N	\N	\N	\N	f	\N	2025-12-14 20:48:20+00	2026-04-23 01:39:39.818334+00	12.0000	minutes
200	humanin	20	MAPRGFSCLLLLTSEIDLPVKRRA	330936-69-1	Humanin is a mitochondria-derived peptide present in an astounding amount of species. It was the first discovered mitochondria-derived peptide. Interest rose when it was noted that overexpression of humanin has showed increased lifespan of nematode's.	Humanin has been shown to interact with Amyloid-Beta, Bax and IGFBP3 in screenings for protein's that interact with them. It dose-dependantly promotes chaperone-mediated autophagy, protects against apoptosis, decreases inflammatory cytokines, promotes cell survival and increases insulin sensitivity. It protects neurons from amyloid-beta toxicity. It also protects against oxidative stress and atherosclerosis.	https://pubchem.ncbi.nlm.nih.gov/image/imgsrv.fcgi?cid=16131438&t=l	H-Met-Ala-Pro-Arg-Gly-Phe-Ser-Cys-Leu-Leu-Leu-Leu-Thr-Ser-Glu-Ile-Asp-Leu-Pro-Val-Lys-Arg-Arg-Ala-OH	2687.2 g/mol	\N	Cognitive Decline, Diabetes, Anti-Aging, Prion Disease, TBI, Cardiovascular Health	C119H204N34O32S2	Humanin	\N	\N	\N	\N	\N	\N	\N	\N	\N	\N	\N	\N	\N	\N	\N	\N	\N	f	\N	2025-12-05 18:17:18+00	2026-04-23 01:39:39.818334+00	0.5000	hours
210	vosoritide	27	PGQEHPNARKYKGANKKGLSKGCFGLKLDRIGSMSGLGC	Voxzogo, BMN-111	Vosoritide is a medication for treatment of Achondroplasia which mainly presents as dwarfism.	Vosoritide is a long acting analog of C-type natriuretic peptide. By binding to NPR-B it inhibits FGFR3 which would otherwise slow down or stop cartilage and bone growth when activated by FGF-1/2 by inhibiting proliferation and differentiation of chondrocytes.	https://pubchem.ncbi.nlm.nih.gov/image/imgsrv.fcgi?cid=119058036&t=l	H-Pro-Gly-Gln-Glu-His-Pro-Asn-Ala-Arg-Lys-Tyr-Lys-Gly-Ala-Asn-Lys-Lys-Gly-Leu-Ser-Lys-Gly-Cys(1)-Phe-Gly-Leu-Lys-Leu-Asp-Arg-Ile-Gly-Ser-Met-Ser-Gly-Leu-Gly-Cys(1)-OH	4102.78 g/mol	\N	Height Enhancement	C176H290N56O51S3	Vosoritide	\N	\N	\N	\N	\N	\N	\N	\N	\N	\N	\N	\N	\N	\N	\N	\N	\N	f	\N	2025-12-16 22:06:28+00	2026-04-23 01:39:39.818334+00	0.4000	hours
20	glutathione	5	Glu-Cys-Gly	GSH, L-Glutathione, Glutathione reduced	Glutathione is the master antioxidant found in every cell of the human body. This tripeptide plays a crucial role in protecting cells from oxidative stress, supporting immune function, and facilitating detoxification processes.	Glutathione neutralizes free radicals and reactive oxygen species through electron donation. It also serves as a cofactor for various enzymes involved in detoxification, supports regeneration of other antioxidants like vitamins C and E, and maintains cellular redox balance.	https://imagedelivery.net/ey2i3L8oxd4cGMILqBg6mg/6be95ccd-1a09-40ec-f59d-25e6771c3600/public	Î³-Glutamylcysteinylglycine	307.32 g/mol	\N	Anti-aging, detoxification, immune support, neurodegenerative diseases, liver health, skin whitening	C10H17N3O6S	Glutathione	\N	\N	\N	\N	\N	\N	\N	\N	\N	\N	\N	\N	\N	\N	\N	\N	\N	f	\N	2025-04-15 02:28:26+00	2026-04-23 01:39:39.818334+00	30.0000	minutes
113	5-amino-1mq	19	C[N+]1=CC=CC2=C(C=CC=C12)N.[I-]	5-Amino-1-methylquinolinium, 5-Amino-1-methylquinolin-1-ium	5-Amino-1MQ is a small molecule compound known for its potential role in inhibiting nicotinamide N-methyltransferase (NNMT), an enzyme linked to metabolic disorders, obesity, and certain cancers.	5-Amino-1MQ exerts its effects through inhibiting NNMT (nicotinamide N-methyltransferase).\r\nNNMT regulates methylation potential in cells and influences metabolic pathways. Inhibition may: Promote fat cell metabolism, Improve energy expenditure, Reduce cancer cell proliferation.	https://www.sigmaaldrich.com/deepweb/assets/sigmaaldrich/product/structures/156/298/6f0f92f1-873e-4f19-ad23-a69bd02a2194/640/6f0f92f1-873e-4f19-ad23-a69bd02a2194.png	5-Amino-1-methylquinolin-1-ium	159.21 g/mol	\N	Metabolic Disorder, Obesity, BodyBuilding, Cancer, Insulin Resistance	C10H11N2	5-Amino-1MQ	\N	\N	\N	\N	\N	\N	\N	\N	\N	\N	\N	\N	\N	\N	\N	\N	\N	f	\N	2025-08-14 22:15:22+00	2026-04-23 01:39:39.818334+00	7.0000	hours
181	cerebrolysin	25	\N	Cerebroprotein hydrolysate	Cerebrolysin is a neuropeptide complex extracted from porcine brain, composing of peptides and amino acids that produce neurotrophic and neuroprotective effects.	Cerebrolysin includes endogenous neuropeptides like BDNF, GDNF, NGF, CNTF which bind to their receptors to produce neurotrophic and neuroprotective effects. Specific molecular pathways are not clear.	\N	\N	\N	\N	Cognitive Dnhancement, Cognitive Decline, Addiction, Habits Formation	\N	Cerebrolysin	\N	\N	\N	\N	\N	\N	\N	\N	\N	\N	\N	\N	\N	\N	\N	\N	\N	f	\N	2025-11-04 00:12:58+00	2026-04-23 01:39:39.818334+00	10.0000	minutes
\.


--
-- Data for Name: protocol_application_places; Type: TABLE DATA; Schema: public; Owner: -
--

COPY public.protocol_application_places (id, protocol_id, application_place_id, recommendation_level, notes, created_at, updated_at) FROM stdin;
\.


--
-- Data for Name: protocol_dosage_benefits; Type: TABLE DATA; Schema: public; Owner: -
--

COPY public.protocol_dosage_benefits (id, protocol_dosage_id, benefit_id, potency, onset_time, peak_effect_time, evidence_quality, citations, notes, sort_order, is_active, created_at, updated_at) FROM stdin;
\.


--
-- Data for Name: protocol_dosage_side_effects; Type: TABLE DATA; Schema: public; Owner: -
--

COPY public.protocol_dosage_side_effects (id, protocol_dosage_id, side_effect_id, likelihood, notes, created_at, updated_at) FROM stdin;
2703	1648	2	uncommon	\N	2025-09-08 01:12:59+00	2025-09-08 01:12:59+00
2704	1648	1	uncommon	\N	2025-09-08 01:12:59+00	2025-09-08 01:12:59+00
2705	1648	3	uncommon	\N	2025-09-08 01:12:59+00	2025-09-08 01:12:59+00
2706	1648	16	uncommon	\N	2025-09-08 01:12:59+00	2025-09-08 01:12:59+00
2707	1648	28	uncommon	\N	2025-09-08 01:12:59+00	2025-09-08 01:12:59+00
2708	1648	4	uncommon	\N	2025-09-08 01:12:59+00	2025-09-08 01:12:59+00
2709	1649	2	uncommon	\N	2025-09-08 01:12:59+00	2025-09-08 01:12:59+00
2710	1649	1	uncommon	\N	2025-09-08 01:12:59+00	2025-09-08 01:12:59+00
2711	1649	3	uncommon	\N	2025-09-08 01:12:59+00	2025-09-08 01:12:59+00
2712	1649	16	uncommon	\N	2025-09-08 01:12:59+00	2025-09-08 01:12:59+00
2713	1649	28	uncommon	\N	2025-09-08 01:12:59+00	2025-09-08 01:12:59+00
2714	1649	4	uncommon	\N	2025-09-08 01:12:59+00	2025-09-08 01:12:59+00
2715	1650	2	uncommon	\N	2025-09-08 01:12:59+00	2025-09-08 01:12:59+00
2716	1650	1	uncommon	\N	2025-09-08 01:12:59+00	2025-09-08 01:12:59+00
2717	1650	3	uncommon	\N	2025-09-08 01:12:59+00	2025-09-08 01:12:59+00
2718	1650	16	uncommon	\N	2025-09-08 01:12:59+00	2025-09-08 01:12:59+00
2719	1650	28	uncommon	\N	2025-09-08 01:12:59+00	2025-09-08 01:12:59+00
2720	1650	4	uncommon	\N	2025-09-08 01:12:59+00	2025-09-08 01:12:59+00
2721	1651	2	uncommon	\N	2025-09-08 01:12:59+00	2025-09-08 01:12:59+00
2722	1651	1	uncommon	\N	2025-09-08 01:12:59+00	2025-09-08 01:12:59+00
2723	1651	3	uncommon	\N	2025-09-08 01:12:59+00	2025-09-08 01:12:59+00
2724	1651	16	uncommon	\N	2025-09-08 01:12:59+00	2025-09-08 01:12:59+00
2725	1651	28	uncommon	\N	2025-09-08 01:12:59+00	2025-09-08 01:12:59+00
2726	1651	4	uncommon	\N	2025-09-08 01:12:59+00	2025-09-08 01:12:59+00
3219	1794	27	uncommon	\N	2025-09-08 19:58:33+00	2025-09-08 19:58:33+00
3220	1794	2	uncommon	\N	2025-09-08 19:58:33+00	2025-09-08 19:58:33+00
3221	1794	1	uncommon	\N	2025-09-08 19:58:33+00	2025-09-08 19:58:33+00
3222	1794	3	uncommon	\N	2025-09-08 19:58:33+00	2025-09-08 19:58:33+00
3223	1794	4	uncommon	\N	2025-09-08 19:58:33+00	2025-09-08 19:58:33+00
3224	1795	27	uncommon	\N	2025-09-08 19:58:33+00	2025-09-08 19:58:33+00
3225	1795	2	uncommon	\N	2025-09-08 19:58:33+00	2025-09-08 19:58:33+00
3226	1795	1	uncommon	\N	2025-09-08 19:58:33+00	2025-09-08 19:58:33+00
3227	1795	3	uncommon	\N	2025-09-08 19:58:33+00	2025-09-08 19:58:33+00
3228	1795	4	uncommon	\N	2025-09-08 19:58:33+00	2025-09-08 19:58:33+00
3271	1804	27	uncommon	\N	2025-09-08 20:01:53+00	2025-09-08 20:01:53+00
3272	1804	2	uncommon	\N	2025-09-08 20:01:53+00	2025-09-08 20:01:53+00
3273	1804	1	uncommon	\N	2025-09-08 20:01:53+00	2025-09-08 20:01:53+00
3274	1804	3	uncommon	\N	2025-09-08 20:01:53+00	2025-09-08 20:01:53+00
3275	1804	4	uncommon	\N	2025-09-08 20:01:53+00	2025-09-08 20:01:53+00
3276	1805	27	uncommon	\N	2025-09-08 20:01:53+00	2025-09-08 20:01:53+00
3277	1805	2	uncommon	\N	2025-09-08 20:01:53+00	2025-09-08 20:01:53+00
3278	1805	1	uncommon	\N	2025-09-08 20:01:53+00	2025-09-08 20:01:53+00
3279	1805	3	uncommon	\N	2025-09-08 20:01:53+00	2025-09-08 20:01:53+00
3280	1805	30	uncommon	\N	2025-09-08 20:01:53+00	2025-09-08 20:01:53+00
3281	1805	4	uncommon	\N	2025-09-08 20:01:53+00	2025-09-08 20:01:53+00
3282	1806	27	uncommon	\N	2025-09-08 20:01:53+00	2025-09-08 20:01:53+00
3283	1806	2	uncommon	\N	2025-09-08 20:01:53+00	2025-09-08 20:01:53+00
3284	1806	1	uncommon	\N	2025-09-08 20:01:53+00	2025-09-08 20:01:53+00
3285	1806	3	uncommon	\N	2025-09-08 20:01:53+00	2025-09-08 20:01:53+00
3286	1806	30	uncommon	\N	2025-09-08 20:01:53+00	2025-09-08 20:01:53+00
3287	1806	4	uncommon	\N	2025-09-08 20:01:53+00	2025-09-08 20:01:53+00
3337	1827	27	uncommon	\N	2025-09-08 20:06:11+00	2025-09-08 20:06:11+00
3338	1827	2	uncommon	\N	2025-09-08 20:06:11+00	2025-09-08 20:06:11+00
3339	1827	3	uncommon	\N	2025-09-08 20:06:11+00	2025-09-08 20:06:11+00
3340	1828	27	uncommon	\N	2025-09-08 20:06:11+00	2025-09-08 20:06:11+00
3341	1828	2	uncommon	\N	2025-09-08 20:06:11+00	2025-09-08 20:06:11+00
3342	1828	3	uncommon	\N	2025-09-08 20:06:11+00	2025-09-08 20:06:11+00
3544	1870	27	uncommon	\N	2025-09-08 20:14:15+00	2025-09-08 20:14:15+00
3545	1870	2	uncommon	\N	2025-09-08 20:14:15+00	2025-09-08 20:14:15+00
3546	1871	27	uncommon	\N	2025-09-08 20:14:15+00	2025-09-08 20:14:15+00
3547	1871	2	uncommon	\N	2025-09-08 20:14:15+00	2025-09-08 20:14:15+00
3548	1872	27	uncommon	\N	2025-09-08 20:14:15+00	2025-09-08 20:14:15+00
3549	1872	2	uncommon	\N	2025-09-08 20:14:15+00	2025-09-08 20:14:15+00
3598	1887	27	uncommon	\N	2025-09-09 16:03:09+00	2025-09-09 16:03:09+00
3599	1888	27	uncommon	\N	2025-09-09 16:03:09+00	2025-09-09 16:03:09+00
3600	1889	27	uncommon	\N	2025-09-09 16:03:09+00	2025-09-09 16:03:09+00
3685	1923	27	uncommon	\N	2025-09-10 05:34:16+00	2025-09-10 05:34:16+00
3686	1923	2	uncommon	\N	2025-09-10 05:34:16+00	2025-09-10 05:34:16+00
3687	1923	3	uncommon	\N	2025-09-10 05:34:16+00	2025-09-10 05:34:16+00
3688	1923	4	uncommon	\N	2025-09-10 05:34:16+00	2025-09-10 05:34:16+00
3689	1924	27	uncommon	\N	2025-09-10 05:34:16+00	2025-09-10 05:34:16+00
3690	1924	2	uncommon	\N	2025-09-10 05:34:16+00	2025-09-10 05:34:16+00
3691	1924	3	uncommon	\N	2025-09-10 05:34:16+00	2025-09-10 05:34:16+00
3692	1924	4	uncommon	\N	2025-09-10 05:34:16+00	2025-09-10 05:34:16+00
3693	1925	27	uncommon	\N	2025-09-10 05:34:16+00	2025-09-10 05:34:16+00
3694	1925	2	uncommon	\N	2025-09-10 05:34:16+00	2025-09-10 05:34:16+00
3695	1925	3	uncommon	\N	2025-09-10 05:34:16+00	2025-09-10 05:34:16+00
3696	1925	4	uncommon	\N	2025-09-10 05:34:16+00	2025-09-10 05:34:16+00
3697	1926	27	uncommon	\N	2025-09-10 05:34:16+00	2025-09-10 05:34:16+00
3698	1926	2	uncommon	\N	2025-09-10 05:34:16+00	2025-09-10 05:34:16+00
3699	1926	3	uncommon	\N	2025-09-10 05:34:16+00	2025-09-10 05:34:16+00
3700	1926	4	uncommon	\N	2025-09-10 05:34:16+00	2025-09-10 05:34:16+00
3701	1927	29	uncommon	\N	2025-09-11 16:35:35+00	2025-09-11 16:35:35+00
3702	1927	27	uncommon	\N	2025-09-11 16:35:35+00	2025-09-11 16:35:35+00
3703	1928	29	uncommon	\N	2025-09-11 16:35:35+00	2025-09-11 16:35:35+00
3704	1928	27	uncommon	\N	2025-09-11 16:35:35+00	2025-09-11 16:35:35+00
3705	1929	29	uncommon	\N	2025-09-11 16:35:35+00	2025-09-11 16:35:35+00
3706	1929	27	uncommon	\N	2025-09-11 16:35:35+00	2025-09-11 16:35:35+00
3731	1936	27	uncommon	\N	2025-09-11 17:32:31+00	2025-09-11 17:32:31+00
3732	1936	20	uncommon	\N	2025-09-11 17:32:31+00	2025-09-11 17:32:31+00
3733	1936	32	uncommon	\N	2025-09-11 17:32:31+00	2025-09-11 17:32:31+00
3734	1936	2	uncommon	\N	2025-09-11 17:32:31+00	2025-09-11 17:32:31+00
3735	1937	27	uncommon	\N	2025-09-11 17:32:31+00	2025-09-11 17:32:31+00
3736	1937	20	uncommon	\N	2025-09-11 17:32:31+00	2025-09-11 17:32:31+00
3737	1937	32	uncommon	\N	2025-09-11 17:32:31+00	2025-09-11 17:32:31+00
3738	1937	2	uncommon	\N	2025-09-11 17:32:31+00	2025-09-11 17:32:31+00
3739	1938	27	uncommon	\N	2025-09-11 17:32:31+00	2025-09-11 17:32:31+00
3740	1938	20	uncommon	\N	2025-09-11 17:32:31+00	2025-09-11 17:32:31+00
3741	1938	32	uncommon	\N	2025-09-11 17:32:31+00	2025-09-11 17:32:31+00
3742	1938	2	uncommon	\N	2025-09-11 17:32:31+00	2025-09-11 17:32:31+00
3787	1955	27	uncommon	\N	2025-09-16 16:18:41+00	2025-09-16 16:18:41+00
3788	1955	2	uncommon	\N	2025-09-16 16:18:41+00	2025-09-16 16:18:41+00
3789	1955	1	uncommon	\N	2025-09-16 16:18:41+00	2025-09-16 16:18:41+00
3790	1955	3	uncommon	\N	2025-09-16 16:18:41+00	2025-09-16 16:18:41+00
3791	1955	4	uncommon	\N	2025-09-16 16:18:41+00	2025-09-16 16:18:41+00
3792	1956	27	uncommon	\N	2025-09-16 16:18:41+00	2025-09-16 16:18:41+00
3793	1956	2	uncommon	\N	2025-09-16 16:18:41+00	2025-09-16 16:18:41+00
3794	1956	1	uncommon	\N	2025-09-16 16:18:41+00	2025-09-16 16:18:41+00
3795	1956	3	uncommon	\N	2025-09-16 16:18:41+00	2025-09-16 16:18:41+00
3796	1956	4	uncommon	\N	2025-09-16 16:18:41+00	2025-09-16 16:18:41+00
3821	1963	27	uncommon	\N	2025-09-17 01:36:50+00	2025-09-17 01:36:50+00
3822	1963	32	uncommon	\N	2025-09-17 01:36:50+00	2025-09-17 01:36:50+00
3823	1963	2	uncommon	\N	2025-09-17 01:36:50+00	2025-09-17 01:36:50+00
3824	1963	3	uncommon	\N	2025-09-17 01:36:50+00	2025-09-17 01:36:50+00
3825	1964	27	uncommon	\N	2025-09-17 01:36:50+00	2025-09-17 01:36:50+00
3826	1964	32	uncommon	\N	2025-09-17 01:36:50+00	2025-09-17 01:36:50+00
3827	1964	2	uncommon	\N	2025-09-17 01:36:50+00	2025-09-17 01:36:50+00
3828	1964	3	uncommon	\N	2025-09-17 01:36:50+00	2025-09-17 01:36:50+00
3829	1965	27	uncommon	\N	2025-09-17 01:36:50+00	2025-09-17 01:36:50+00
3830	1965	32	uncommon	\N	2025-09-17 01:36:50+00	2025-09-17 01:36:50+00
3831	1965	2	uncommon	\N	2025-09-17 01:36:50+00	2025-09-17 01:36:50+00
3832	1965	3	uncommon	\N	2025-09-17 01:36:50+00	2025-09-17 01:36:50+00
3833	1966	27	uncommon	\N	2025-09-17 01:39:29+00	2025-09-17 01:39:29+00
3834	1966	2	uncommon	\N	2025-09-17 01:39:29+00	2025-09-17 01:39:29+00
3835	1966	3	uncommon	\N	2025-09-17 01:39:29+00	2025-09-17 01:39:29+00
3836	1966	4	uncommon	\N	2025-09-17 01:39:29+00	2025-09-17 01:39:29+00
3837	1967	27	uncommon	\N	2025-09-17 01:39:29+00	2025-09-17 01:39:29+00
3838	1967	2	uncommon	\N	2025-09-17 01:39:29+00	2025-09-17 01:39:29+00
3839	1967	3	uncommon	\N	2025-09-17 01:39:29+00	2025-09-17 01:39:29+00
3840	1967	4	uncommon	\N	2025-09-17 01:39:29+00	2025-09-17 01:39:29+00
3841	1968	27	uncommon	\N	2025-09-17 01:39:29+00	2025-09-17 01:39:29+00
3842	1968	2	uncommon	\N	2025-09-17 01:39:29+00	2025-09-17 01:39:29+00
3843	1968	3	uncommon	\N	2025-09-17 01:39:29+00	2025-09-17 01:39:29+00
3844	1968	4	uncommon	\N	2025-09-17 01:39:29+00	2025-09-17 01:39:29+00
3854	1972	27	uncommon	\N	2025-09-20 23:37:48+00	2025-09-20 23:37:48+00
3855	1972	3	uncommon	\N	2025-09-20 23:37:48+00	2025-09-20 23:37:48+00
3856	1972	4	uncommon	\N	2025-09-20 23:37:48+00	2025-09-20 23:37:48+00
3857	1973	27	uncommon	\N	2025-09-20 23:37:48+00	2025-09-20 23:37:48+00
3858	1973	3	uncommon	\N	2025-09-20 23:37:48+00	2025-09-20 23:37:48+00
3859	1973	4	uncommon	\N	2025-09-20 23:37:48+00	2025-09-20 23:37:48+00
3860	1974	27	uncommon	\N	2025-09-20 23:37:48+00	2025-09-20 23:37:48+00
3861	1974	3	uncommon	\N	2025-09-20 23:37:48+00	2025-09-20 23:37:48+00
3862	1974	4	uncommon	\N	2025-09-20 23:37:48+00	2025-09-20 23:37:48+00
3863	1975	27	uncommon	\N	2025-09-20 23:37:48+00	2025-09-20 23:37:48+00
3864	1975	3	uncommon	\N	2025-09-20 23:37:48+00	2025-09-20 23:37:48+00
3865	1975	4	uncommon	\N	2025-09-20 23:37:48+00	2025-09-20 23:37:48+00
3866	1976	27	uncommon	\N	2025-09-20 23:44:02+00	2025-09-20 23:44:02+00
3867	1976	3	uncommon	\N	2025-09-20 23:44:02+00	2025-09-20 23:44:02+00
3868	1976	4	uncommon	\N	2025-09-20 23:44:02+00	2025-09-20 23:44:02+00
3869	1977	27	uncommon	\N	2025-09-20 23:44:02+00	2025-09-20 23:44:02+00
3870	1977	3	uncommon	\N	2025-09-20 23:44:02+00	2025-09-20 23:44:02+00
3871	1977	4	uncommon	\N	2025-09-20 23:44:02+00	2025-09-20 23:44:02+00
3872	1978	27	uncommon	\N	2025-09-20 23:44:02+00	2025-09-20 23:44:02+00
3873	1978	3	uncommon	\N	2025-09-20 23:44:02+00	2025-09-20 23:44:02+00
3874	1978	4	uncommon	\N	2025-09-20 23:44:02+00	2025-09-20 23:44:02+00
3875	1979	27	uncommon	\N	2025-09-20 23:54:27+00	2025-09-20 23:54:27+00
3876	1979	3	uncommon	\N	2025-09-20 23:54:27+00	2025-09-20 23:54:27+00
3877	1979	4	uncommon	\N	2025-09-20 23:54:27+00	2025-09-20 23:54:27+00
3878	1980	27	uncommon	\N	2025-09-20 23:54:27+00	2025-09-20 23:54:27+00
3879	1980	3	uncommon	\N	2025-09-20 23:54:27+00	2025-09-20 23:54:27+00
3880	1980	4	uncommon	\N	2025-09-20 23:54:27+00	2025-09-20 23:54:27+00
3881	1981	27	uncommon	\N	2025-09-20 23:54:27+00	2025-09-20 23:54:27+00
3882	1981	3	uncommon	\N	2025-09-20 23:54:27+00	2025-09-20 23:54:27+00
3883	1981	4	uncommon	\N	2025-09-20 23:54:27+00	2025-09-20 23:54:27+00
3884	1982	27	uncommon	\N	2025-09-21 00:01:52+00	2025-09-21 00:01:52+00
3885	1982	3	uncommon	\N	2025-09-21 00:01:52+00	2025-09-21 00:01:52+00
3886	1982	4	uncommon	\N	2025-09-21 00:01:52+00	2025-09-21 00:01:52+00
3887	1983	27	uncommon	\N	2025-09-21 00:01:52+00	2025-09-21 00:01:52+00
3888	1983	3	uncommon	\N	2025-09-21 00:01:52+00	2025-09-21 00:01:52+00
3889	1983	4	uncommon	\N	2025-09-21 00:01:52+00	2025-09-21 00:01:52+00
3890	1984	27	uncommon	\N	2025-09-21 00:01:52+00	2025-09-21 00:01:52+00
3891	1984	3	uncommon	\N	2025-09-21 00:01:52+00	2025-09-21 00:01:52+00
3892	1984	4	uncommon	\N	2025-09-21 00:01:52+00	2025-09-21 00:01:52+00
3893	1985	27	uncommon	\N	2025-09-21 00:10:12+00	2025-09-21 00:10:12+00
3894	1985	3	uncommon	\N	2025-09-21 00:10:12+00	2025-09-21 00:10:12+00
3895	1985	4	uncommon	\N	2025-09-21 00:10:12+00	2025-09-21 00:10:12+00
3896	1986	27	uncommon	\N	2025-09-21 00:10:12+00	2025-09-21 00:10:12+00
3897	1986	3	uncommon	\N	2025-09-21 00:10:12+00	2025-09-21 00:10:12+00
3898	1986	4	uncommon	\N	2025-09-21 00:10:12+00	2025-09-21 00:10:12+00
3899	1987	27	uncommon	\N	2025-09-21 00:10:12+00	2025-09-21 00:10:12+00
3900	1987	3	uncommon	\N	2025-09-21 00:10:12+00	2025-09-21 00:10:12+00
3901	1987	4	uncommon	\N	2025-09-21 00:10:12+00	2025-09-21 00:10:12+00
4885	2319	26	uncommon	\N	2025-09-29 07:34:42+00	2025-09-29 07:34:42+00
4886	2319	25	uncommon	\N	2025-09-29 07:34:42+00	2025-09-29 07:34:42+00
4887	2319	2	uncommon	\N	2025-09-29 07:34:42+00	2025-09-29 07:34:42+00
4888	2319	1	uncommon	\N	2025-09-29 07:34:42+00	2025-09-29 07:34:42+00
4889	2319	3	uncommon	\N	2025-09-29 07:34:42+00	2025-09-29 07:34:42+00
4890	2319	4	uncommon	\N	2025-09-29 07:34:42+00	2025-09-29 07:34:42+00
4891	2320	26	uncommon	\N	2025-09-29 07:34:42+00	2025-09-29 07:34:42+00
4892	2320	25	uncommon	\N	2025-09-29 07:34:42+00	2025-09-29 07:34:42+00
4893	2320	2	uncommon	\N	2025-09-29 07:34:42+00	2025-09-29 07:34:42+00
4894	2320	1	uncommon	\N	2025-09-29 07:34:42+00	2025-09-29 07:34:42+00
4895	2320	3	uncommon	\N	2025-09-29 07:34:42+00	2025-09-29 07:34:42+00
4896	2320	4	uncommon	\N	2025-09-29 07:34:42+00	2025-09-29 07:34:42+00
4897	2321	26	uncommon	\N	2025-09-29 07:34:42+00	2025-09-29 07:34:42+00
4898	2321	25	uncommon	\N	2025-09-29 07:34:42+00	2025-09-29 07:34:42+00
4899	2321	2	uncommon	\N	2025-09-29 07:34:42+00	2025-09-29 07:34:42+00
4900	2321	1	uncommon	\N	2025-09-29 07:34:42+00	2025-09-29 07:34:42+00
4901	2321	3	uncommon	\N	2025-09-29 07:34:42+00	2025-09-29 07:34:42+00
4902	2321	4	uncommon	\N	2025-09-29 07:34:42+00	2025-09-29 07:34:42+00
4903	2322	26	uncommon	\N	2025-09-29 07:34:42+00	2025-09-29 07:34:42+00
4904	2322	25	uncommon	\N	2025-09-29 07:34:42+00	2025-09-29 07:34:42+00
4905	2322	2	uncommon	\N	2025-09-29 07:34:42+00	2025-09-29 07:34:42+00
4906	2322	1	uncommon	\N	2025-09-29 07:34:42+00	2025-09-29 07:34:42+00
4907	2322	3	uncommon	\N	2025-09-29 07:34:42+00	2025-09-29 07:34:42+00
4908	2322	4	uncommon	\N	2025-09-29 07:34:42+00	2025-09-29 07:34:42+00
4909	2323	26	uncommon	\N	2025-09-29 07:34:42+00	2025-09-29 07:34:42+00
4910	2323	25	uncommon	\N	2025-09-29 07:34:42+00	2025-09-29 07:34:42+00
4911	2323	2	uncommon	\N	2025-09-29 07:34:42+00	2025-09-29 07:34:42+00
4912	2323	1	uncommon	\N	2025-09-29 07:34:42+00	2025-09-29 07:34:42+00
4913	2323	3	uncommon	\N	2025-09-29 07:34:42+00	2025-09-29 07:34:42+00
4914	2323	4	uncommon	\N	2025-09-29 07:34:42+00	2025-09-29 07:34:42+00
4915	2324	26	uncommon	\N	2025-09-29 07:34:42+00	2025-09-29 07:34:42+00
4916	2324	25	uncommon	\N	2025-09-29 07:34:42+00	2025-09-29 07:34:42+00
4917	2324	2	uncommon	\N	2025-09-29 07:34:42+00	2025-09-29 07:34:42+00
4918	2324	1	uncommon	\N	2025-09-29 07:34:42+00	2025-09-29 07:34:42+00
4919	2324	3	uncommon	\N	2025-09-29 07:34:42+00	2025-09-29 07:34:42+00
4920	2324	4	uncommon	\N	2025-09-29 07:34:42+00	2025-09-29 07:34:42+00
4921	2325	26	uncommon	\N	2025-09-29 07:34:42+00	2025-09-29 07:34:42+00
4922	2325	25	uncommon	\N	2025-09-29 07:34:42+00	2025-09-29 07:34:42+00
4923	2325	2	uncommon	\N	2025-09-29 07:34:42+00	2025-09-29 07:34:42+00
4924	2325	1	uncommon	\N	2025-09-29 07:34:42+00	2025-09-29 07:34:42+00
4925	2325	3	uncommon	\N	2025-09-29 07:34:42+00	2025-09-29 07:34:42+00
4926	2325	4	uncommon	\N	2025-09-29 07:34:42+00	2025-09-29 07:34:42+00
5462	2490	23	uncommon	\N	2025-10-05 11:14:53+00	2025-10-05 11:14:53+00
5463	2490	14	uncommon	\N	2025-10-05 11:14:53+00	2025-10-05 11:14:53+00
5464	2490	1	uncommon	\N	2025-10-05 11:14:53+00	2025-10-05 11:14:53+00
5465	2491	14	uncommon	\N	2025-10-05 11:14:53+00	2025-10-05 11:14:53+00
5466	2491	1	uncommon	\N	2025-10-05 11:14:53+00	2025-10-05 11:14:53+00
5467	2491	23	uncommon	\N	2025-10-05 11:14:53+00	2025-10-05 11:14:53+00
5468	2492	23	uncommon	\N	2025-10-05 11:14:53+00	2025-10-05 11:14:53+00
5469	2492	1	uncommon	\N	2025-10-05 11:14:53+00	2025-10-05 11:14:53+00
5470	2492	14	uncommon	\N	2025-10-05 11:14:53+00	2025-10-05 11:14:53+00
5471	2493	23	uncommon	\N	2025-10-05 11:14:53+00	2025-10-05 11:14:53+00
5472	2493	1	uncommon	\N	2025-10-05 11:14:53+00	2025-10-05 11:14:53+00
5473	2493	14	uncommon	\N	2025-10-05 11:14:53+00	2025-10-05 11:14:53+00
6451	2816	20	uncommon	\N	2025-11-02 04:16:00+00	2025-11-02 04:16:00+00
6452	2816	2	uncommon	\N	2025-11-02 04:16:00+00	2025-11-02 04:16:00+00
6453	2816	1	uncommon	\N	2025-11-02 04:16:00+00	2025-11-02 04:16:00+00
6454	2816	3	uncommon	\N	2025-11-02 04:16:00+00	2025-11-02 04:16:00+00
6455	2816	4	uncommon	\N	2025-11-02 04:16:00+00	2025-11-02 04:16:00+00
6456	2817	20	uncommon	\N	2025-11-02 04:16:00+00	2025-11-02 04:16:00+00
6457	2817	2	uncommon	\N	2025-11-02 04:16:00+00	2025-11-02 04:16:00+00
6458	2817	1	uncommon	\N	2025-11-02 04:16:00+00	2025-11-02 04:16:00+00
6459	2817	3	uncommon	\N	2025-11-02 04:16:00+00	2025-11-02 04:16:00+00
6460	2817	4	uncommon	\N	2025-11-02 04:16:00+00	2025-11-02 04:16:00+00
6461	2818	20	uncommon	\N	2025-11-02 04:16:00+00	2025-11-02 04:16:00+00
6462	2818	2	uncommon	\N	2025-11-02 04:16:00+00	2025-11-02 04:16:00+00
6463	2818	1	uncommon	\N	2025-11-02 04:16:00+00	2025-11-02 04:16:00+00
6464	2818	3	uncommon	\N	2025-11-02 04:16:00+00	2025-11-02 04:16:00+00
6465	2818	4	uncommon	\N	2025-11-02 04:16:00+00	2025-11-02 04:16:00+00
6466	2819	20	uncommon	\N	2025-11-02 04:16:00+00	2025-11-02 04:16:00+00
6467	2819	2	uncommon	\N	2025-11-02 04:16:00+00	2025-11-02 04:16:00+00
6468	2819	1	uncommon	\N	2025-11-02 04:16:00+00	2025-11-02 04:16:00+00
6469	2819	3	uncommon	\N	2025-11-02 04:16:00+00	2025-11-02 04:16:00+00
6470	2819	4	uncommon	\N	2025-11-02 04:16:00+00	2025-11-02 04:16:00+00
6929	2910	40	uncommon	\N	2025-11-04 18:59:11+00	2025-11-04 18:59:11+00
6930	2910	2	uncommon	\N	2025-11-04 18:59:11+00	2025-11-04 18:59:11+00
6931	2910	3	uncommon	\N	2025-11-04 18:59:11+00	2025-11-04 18:59:11+00
6932	2910	16	uncommon	\N	2025-11-04 18:59:11+00	2025-11-04 18:59:11+00
6933	2911	40	uncommon	\N	2025-11-04 18:59:11+00	2025-11-04 18:59:11+00
6934	2911	2	uncommon	\N	2025-11-04 18:59:11+00	2025-11-04 18:59:11+00
6935	2911	3	uncommon	\N	2025-11-04 18:59:11+00	2025-11-04 18:59:11+00
6936	2911	16	uncommon	\N	2025-11-04 18:59:11+00	2025-11-04 18:59:11+00
6937	2912	40	uncommon	\N	2025-11-04 18:59:11+00	2025-11-04 18:59:11+00
6938	2912	2	uncommon	\N	2025-11-04 18:59:11+00	2025-11-04 18:59:11+00
6939	2912	16	uncommon	\N	2025-11-04 18:59:11+00	2025-11-04 18:59:11+00
6940	2912	3	uncommon	\N	2025-11-04 18:59:11+00	2025-11-04 18:59:11+00
7058	2951	17	uncommon	\N	2025-11-05 05:45:16+00	2025-11-05 05:45:16+00
7059	2951	41	uncommon	\N	2025-11-05 05:45:16+00	2025-11-05 05:45:16+00
7060	2951	2	uncommon	\N	2025-11-05 05:45:16+00	2025-11-05 05:45:16+00
7061	2951	16	uncommon	\N	2025-11-05 05:45:16+00	2025-11-05 05:45:16+00
7062	2952	17	uncommon	\N	2025-11-05 05:45:16+00	2025-11-05 05:45:16+00
7063	2952	41	uncommon	\N	2025-11-05 05:45:16+00	2025-11-05 05:45:16+00
7064	2952	2	uncommon	\N	2025-11-05 05:45:16+00	2025-11-05 05:45:16+00
7065	2952	16	uncommon	\N	2025-11-05 05:45:16+00	2025-11-05 05:45:16+00
7066	2953	17	uncommon	\N	2025-11-05 05:45:16+00	2025-11-05 05:45:16+00
7067	2953	41	uncommon	\N	2025-11-05 05:45:16+00	2025-11-05 05:45:16+00
7068	2953	2	uncommon	\N	2025-11-05 05:45:16+00	2025-11-05 05:45:16+00
7069	2953	16	uncommon	\N	2025-11-05 05:45:16+00	2025-11-05 05:45:16+00
7231	2997	41	uncommon	\N	2025-11-06 21:39:17+00	2025-11-06 21:39:17+00
7232	2997	27	uncommon	\N	2025-11-06 21:39:17+00	2025-11-06 21:39:17+00
7233	2997	2	uncommon	\N	2025-11-06 21:39:17+00	2025-11-06 21:39:17+00
7234	2997	3	uncommon	\N	2025-11-06 21:39:17+00	2025-11-06 21:39:17+00
7235	2997	16	uncommon	\N	2025-11-06 21:39:17+00	2025-11-06 21:39:17+00
7236	2997	28	uncommon	\N	2025-11-06 21:39:17+00	2025-11-06 21:39:17+00
7237	2997	4	uncommon	\N	2025-11-06 21:39:17+00	2025-11-06 21:39:17+00
7238	2997	34	uncommon	\N	2025-11-06 21:39:17+00	2025-11-06 21:39:17+00
7239	2998	41	uncommon	\N	2025-11-06 21:39:17+00	2025-11-06 21:39:17+00
7240	2998	27	uncommon	\N	2025-11-06 21:39:17+00	2025-11-06 21:39:17+00
7241	2998	2	uncommon	\N	2025-11-06 21:39:17+00	2025-11-06 21:39:17+00
7242	2998	3	uncommon	\N	2025-11-06 21:39:17+00	2025-11-06 21:39:17+00
7243	2998	16	uncommon	\N	2025-11-06 21:39:17+00	2025-11-06 21:39:17+00
7244	2998	28	uncommon	\N	2025-11-06 21:39:17+00	2025-11-06 21:39:17+00
7245	2998	4	uncommon	\N	2025-11-06 21:39:17+00	2025-11-06 21:39:17+00
7246	2998	34	uncommon	\N	2025-11-06 21:39:17+00	2025-11-06 21:39:17+00
7247	2999	41	uncommon	\N	2025-11-06 21:39:17+00	2025-11-06 21:39:17+00
7248	2999	27	uncommon	\N	2025-11-06 21:39:17+00	2025-11-06 21:39:17+00
7249	2999	2	uncommon	\N	2025-11-06 21:39:17+00	2025-11-06 21:39:17+00
7250	2999	3	uncommon	\N	2025-11-06 21:39:17+00	2025-11-06 21:39:17+00
7251	2999	16	uncommon	\N	2025-11-06 21:39:17+00	2025-11-06 21:39:17+00
7252	2999	28	uncommon	\N	2025-11-06 21:39:17+00	2025-11-06 21:39:17+00
7253	2999	4	uncommon	\N	2025-11-06 21:39:17+00	2025-11-06 21:39:17+00
7254	2999	34	uncommon	\N	2025-11-06 21:39:17+00	2025-11-06 21:39:17+00
7255	3000	41	uncommon	\N	2025-11-06 21:39:17+00	2025-11-06 21:39:17+00
7256	3000	27	uncommon	\N	2025-11-06 21:39:17+00	2025-11-06 21:39:17+00
7257	3000	2	uncommon	\N	2025-11-06 21:39:17+00	2025-11-06 21:39:17+00
7258	3000	3	uncommon	\N	2025-11-06 21:39:17+00	2025-11-06 21:39:17+00
7259	3000	16	uncommon	\N	2025-11-06 21:39:17+00	2025-11-06 21:39:17+00
7260	3000	28	uncommon	\N	2025-11-06 21:39:17+00	2025-11-06 21:39:17+00
7261	3000	4	uncommon	\N	2025-11-06 21:39:17+00	2025-11-06 21:39:17+00
7262	3000	34	uncommon	\N	2025-11-06 21:39:17+00	2025-11-06 21:39:17+00
7263	3001	41	uncommon	\N	2025-11-06 21:39:17+00	2025-11-06 21:39:17+00
7264	3001	27	uncommon	\N	2025-11-06 21:39:17+00	2025-11-06 21:39:17+00
7265	3001	2	uncommon	\N	2025-11-06 21:39:17+00	2025-11-06 21:39:17+00
7266	3001	3	uncommon	\N	2025-11-06 21:39:17+00	2025-11-06 21:39:17+00
7267	3001	16	uncommon	\N	2025-11-06 21:39:17+00	2025-11-06 21:39:17+00
7268	3001	28	uncommon	\N	2025-11-06 21:39:17+00	2025-11-06 21:39:17+00
7269	3001	4	uncommon	\N	2025-11-06 21:39:17+00	2025-11-06 21:39:17+00
7270	3001	34	uncommon	\N	2025-11-06 21:39:17+00	2025-11-06 21:39:17+00
7296	3016	2	uncommon	\N	2025-11-07 03:35:52+00	2025-11-07 03:35:52+00
7297	3016	3	uncommon	\N	2025-11-07 03:35:52+00	2025-11-07 03:35:52+00
7298	3017	2	uncommon	\N	2025-11-07 03:35:52+00	2025-11-07 03:35:52+00
7299	3017	3	uncommon	\N	2025-11-07 03:35:52+00	2025-11-07 03:35:52+00
7300	3018	3	uncommon	\N	2025-11-07 03:35:52+00	2025-11-07 03:35:52+00
7301	3018	2	uncommon	\N	2025-11-07 03:35:52+00	2025-11-07 03:35:52+00
7323	3040	27	uncommon	\N	2025-11-14 07:52:37+00	2025-11-14 07:52:37+00
7324	3040	14	uncommon	\N	2025-11-14 07:52:37+00	2025-11-14 07:52:37+00
7325	3041	27	uncommon	\N	2025-11-14 07:52:37+00	2025-11-14 07:52:37+00
7326	3041	2	uncommon	\N	2025-11-14 07:52:37+00	2025-11-14 07:52:37+00
7327	3041	14	uncommon	\N	2025-11-14 07:52:37+00	2025-11-14 07:52:37+00
7420	3060	26	uncommon	\N	2025-11-16 02:49:22+00	2025-11-16 02:49:22+00
7421	3060	40	uncommon	\N	2025-11-16 02:49:22+00	2025-11-16 02:49:22+00
7422	3060	17	uncommon	\N	2025-11-16 02:49:22+00	2025-11-16 02:49:22+00
7423	3060	39	uncommon	\N	2025-11-16 02:49:22+00	2025-11-16 02:49:22+00
7424	3060	32	uncommon	\N	2025-11-16 02:49:22+00	2025-11-16 02:49:22+00
7425	3060	2	uncommon	\N	2025-11-16 02:49:22+00	2025-11-16 02:49:22+00
7426	3060	38	uncommon	\N	2025-11-16 02:49:22+00	2025-11-16 02:49:22+00
7427	3060	3	uncommon	\N	2025-11-16 02:49:22+00	2025-11-16 02:49:22+00
7428	3060	28	uncommon	\N	2025-11-16 02:49:22+00	2025-11-16 02:49:22+00
7429	3060	4	uncommon	\N	2025-11-16 02:49:22+00	2025-11-16 02:49:22+00
7430	3061	26	uncommon	\N	2025-11-16 02:49:22+00	2025-11-16 02:49:22+00
7431	3061	40	uncommon	\N	2025-11-16 02:49:22+00	2025-11-16 02:49:22+00
7432	3061	17	uncommon	\N	2025-11-16 02:49:22+00	2025-11-16 02:49:22+00
7433	3061	39	uncommon	\N	2025-11-16 02:49:22+00	2025-11-16 02:49:22+00
7434	3061	32	uncommon	\N	2025-11-16 02:49:22+00	2025-11-16 02:49:22+00
7435	3061	2	uncommon	\N	2025-11-16 02:49:22+00	2025-11-16 02:49:22+00
7436	3061	38	uncommon	\N	2025-11-16 02:49:22+00	2025-11-16 02:49:22+00
7437	3061	3	uncommon	\N	2025-11-16 02:49:22+00	2025-11-16 02:49:22+00
7438	3061	28	uncommon	\N	2025-11-16 02:49:22+00	2025-11-16 02:49:22+00
7439	3061	4	uncommon	\N	2025-11-16 02:49:22+00	2025-11-16 02:49:22+00
7440	3062	26	uncommon	\N	2025-11-16 02:49:22+00	2025-11-16 02:49:22+00
7441	3062	40	uncommon	\N	2025-11-16 02:49:22+00	2025-11-16 02:49:22+00
7442	3062	17	uncommon	\N	2025-11-16 02:49:22+00	2025-11-16 02:49:22+00
7443	3062	39	uncommon	\N	2025-11-16 02:49:22+00	2025-11-16 02:49:22+00
7444	3062	32	uncommon	\N	2025-11-16 02:49:22+00	2025-11-16 02:49:22+00
7445	3062	2	uncommon	\N	2025-11-16 02:49:22+00	2025-11-16 02:49:22+00
7446	3062	38	uncommon	\N	2025-11-16 02:49:22+00	2025-11-16 02:49:22+00
7447	3062	3	uncommon	\N	2025-11-16 02:49:22+00	2025-11-16 02:49:22+00
7448	3062	28	uncommon	\N	2025-11-16 02:49:22+00	2025-11-16 02:49:22+00
7449	3062	4	uncommon	\N	2025-11-16 02:49:22+00	2025-11-16 02:49:22+00
7450	3063	26	uncommon	\N	2025-11-16 02:49:22+00	2025-11-16 02:49:22+00
7451	3063	40	uncommon	\N	2025-11-16 02:49:22+00	2025-11-16 02:49:22+00
7452	3063	17	uncommon	\N	2025-11-16 02:49:22+00	2025-11-16 02:49:22+00
7453	3063	39	uncommon	\N	2025-11-16 02:49:22+00	2025-11-16 02:49:22+00
7454	3063	32	uncommon	\N	2025-11-16 02:49:22+00	2025-11-16 02:49:22+00
7455	3063	2	uncommon	\N	2025-11-16 02:49:22+00	2025-11-16 02:49:22+00
7456	3063	38	uncommon	\N	2025-11-16 02:49:22+00	2025-11-16 02:49:22+00
7457	3063	3	uncommon	\N	2025-11-16 02:49:22+00	2025-11-16 02:49:22+00
7458	3063	28	uncommon	\N	2025-11-16 02:49:22+00	2025-11-16 02:49:22+00
7459	3063	4	uncommon	\N	2025-11-16 02:49:22+00	2025-11-16 02:49:22+00
7624	3116	27	uncommon	\N	2025-11-18 04:03:47+00	2025-11-18 04:03:47+00
7625	3116	15	uncommon	\N	2025-11-18 04:03:47+00	2025-11-18 04:03:47+00
7626	3116	14	uncommon	\N	2025-11-18 04:03:47+00	2025-11-18 04:03:47+00
7627	3116	1	uncommon	\N	2025-11-18 04:03:47+00	2025-11-18 04:03:47+00
7628	3116	28	uncommon	\N	2025-11-18 04:03:47+00	2025-11-18 04:03:47+00
7629	3117	27	uncommon	\N	2025-11-18 04:03:47+00	2025-11-18 04:03:47+00
7630	3117	15	uncommon	\N	2025-11-18 04:03:47+00	2025-11-18 04:03:47+00
7631	3117	14	uncommon	\N	2025-11-18 04:03:47+00	2025-11-18 04:03:47+00
7632	3117	1	uncommon	\N	2025-11-18 04:03:47+00	2025-11-18 04:03:47+00
7633	3117	28	uncommon	\N	2025-11-18 04:03:47+00	2025-11-18 04:03:47+00
7634	3118	27	uncommon	\N	2025-11-18 04:03:47+00	2025-11-18 04:03:47+00
7635	3118	15	uncommon	\N	2025-11-18 04:03:47+00	2025-11-18 04:03:47+00
7636	3118	14	uncommon	\N	2025-11-18 04:03:47+00	2025-11-18 04:03:47+00
7637	3118	1	uncommon	\N	2025-11-18 04:03:47+00	2025-11-18 04:03:47+00
7638	3118	28	uncommon	\N	2025-11-18 04:03:47+00	2025-11-18 04:03:47+00
7639	3119	27	uncommon	\N	2025-11-18 04:03:47+00	2025-11-18 04:03:47+00
7640	3119	15	uncommon	\N	2025-11-18 04:03:47+00	2025-11-18 04:03:47+00
7641	3119	14	uncommon	\N	2025-11-18 04:03:47+00	2025-11-18 04:03:47+00
7642	3119	28	uncommon	\N	2025-11-18 04:03:47+00	2025-11-18 04:03:47+00
7643	3120	27	uncommon	\N	2025-11-18 04:03:47+00	2025-11-18 04:03:47+00
7644	3120	15	uncommon	\N	2025-11-18 04:03:47+00	2025-11-18 04:03:47+00
7645	3120	14	uncommon	\N	2025-11-18 04:03:47+00	2025-11-18 04:03:47+00
7646	3120	28	uncommon	\N	2025-11-18 04:03:47+00	2025-11-18 04:03:47+00
7984	3257	40	uncommon	\N	2025-11-29 11:36:41+00	2025-11-29 11:36:41+00
7985	3257	17	uncommon	\N	2025-11-29 11:36:41+00	2025-11-29 11:36:41+00
7986	3257	25	uncommon	\N	2025-11-29 11:36:41+00	2025-11-29 11:36:41+00
7987	3257	2	uncommon	\N	2025-11-29 11:36:41+00	2025-11-29 11:36:41+00
7988	3257	38	uncommon	\N	2025-11-29 11:36:41+00	2025-11-29 11:36:41+00
7989	3257	3	uncommon	\N	2025-11-29 11:36:41+00	2025-11-29 11:36:41+00
7990	3257	16	uncommon	\N	2025-11-29 11:36:41+00	2025-11-29 11:36:41+00
7991	3257	33	uncommon	\N	2025-11-29 11:36:41+00	2025-11-29 11:36:41+00
7992	3258	40	uncommon	\N	2025-11-29 11:36:41+00	2025-11-29 11:36:41+00
7993	3258	17	uncommon	\N	2025-11-29 11:36:41+00	2025-11-29 11:36:41+00
7994	3258	25	uncommon	\N	2025-11-29 11:36:41+00	2025-11-29 11:36:41+00
7995	3258	2	uncommon	\N	2025-11-29 11:36:41+00	2025-11-29 11:36:41+00
7996	3258	38	uncommon	\N	2025-11-29 11:36:41+00	2025-11-29 11:36:41+00
7997	3258	3	uncommon	\N	2025-11-29 11:36:41+00	2025-11-29 11:36:41+00
7998	3258	16	uncommon	\N	2025-11-29 11:36:41+00	2025-11-29 11:36:41+00
7999	3258	33	uncommon	\N	2025-11-29 11:36:41+00	2025-11-29 11:36:41+00
8000	3259	40	uncommon	\N	2025-11-29 11:36:41+00	2025-11-29 11:36:41+00
8001	3259	17	uncommon	\N	2025-11-29 11:36:41+00	2025-11-29 11:36:41+00
8002	3259	25	uncommon	\N	2025-11-29 11:36:41+00	2025-11-29 11:36:41+00
8003	3259	2	uncommon	\N	2025-11-29 11:36:41+00	2025-11-29 11:36:41+00
8004	3259	38	uncommon	\N	2025-11-29 11:36:41+00	2025-11-29 11:36:41+00
8005	3259	3	uncommon	\N	2025-11-29 11:36:41+00	2025-11-29 11:36:41+00
8006	3259	16	uncommon	\N	2025-11-29 11:36:41+00	2025-11-29 11:36:41+00
8007	3259	33	uncommon	\N	2025-11-29 11:36:41+00	2025-11-29 11:36:41+00
8042	3270	29	uncommon	\N	2025-11-29 12:10:25+00	2025-11-29 12:10:25+00
8043	3270	3	uncommon	\N	2025-11-29 12:10:25+00	2025-11-29 12:10:25+00
8044	3270	37	uncommon	\N	2025-11-29 12:10:25+00	2025-11-29 12:10:25+00
8045	3270	17	uncommon	\N	2025-11-29 12:10:25+00	2025-11-29 12:10:25+00
8046	3270	36	uncommon	\N	2025-11-29 12:10:25+00	2025-11-29 12:10:25+00
8047	3270	44	uncommon	\N	2025-11-29 12:10:25+00	2025-11-29 12:10:25+00
8048	3270	2	uncommon	\N	2025-11-29 12:10:25+00	2025-11-29 12:10:25+00
8049	3270	43	uncommon	\N	2025-11-29 12:10:25+00	2025-11-29 12:10:25+00
8050	3270	28	uncommon	\N	2025-11-29 12:10:25+00	2025-11-29 12:10:25+00
8051	3270	4	uncommon	\N	2025-11-29 12:10:25+00	2025-11-29 12:10:25+00
8052	3271	29	uncommon	\N	2025-11-29 12:10:25+00	2025-11-29 12:10:25+00
8053	3271	3	uncommon	\N	2025-11-29 12:10:25+00	2025-11-29 12:10:25+00
8054	3271	37	uncommon	\N	2025-11-29 12:10:25+00	2025-11-29 12:10:25+00
8055	3271	17	uncommon	\N	2025-11-29 12:10:25+00	2025-11-29 12:10:25+00
8056	3271	36	uncommon	\N	2025-11-29 12:10:25+00	2025-11-29 12:10:25+00
8057	3271	44	uncommon	\N	2025-11-29 12:10:25+00	2025-11-29 12:10:25+00
8058	3271	2	uncommon	\N	2025-11-29 12:10:25+00	2025-11-29 12:10:25+00
8059	3271	43	uncommon	\N	2025-11-29 12:10:25+00	2025-11-29 12:10:25+00
8060	3271	28	uncommon	\N	2025-11-29 12:10:25+00	2025-11-29 12:10:25+00
8061	3271	4	uncommon	\N	2025-11-29 12:10:25+00	2025-11-29 12:10:25+00
8062	3272	29	uncommon	\N	2025-11-29 12:10:25+00	2025-11-29 12:10:25+00
8063	3272	3	uncommon	\N	2025-11-29 12:10:25+00	2025-11-29 12:10:25+00
8064	3272	37	uncommon	\N	2025-11-29 12:10:25+00	2025-11-29 12:10:25+00
8065	3272	17	uncommon	\N	2025-11-29 12:10:25+00	2025-11-29 12:10:25+00
8066	3272	36	uncommon	\N	2025-11-29 12:10:25+00	2025-11-29 12:10:25+00
8067	3272	44	uncommon	\N	2025-11-29 12:10:25+00	2025-11-29 12:10:25+00
8068	3272	2	uncommon	\N	2025-11-29 12:10:25+00	2025-11-29 12:10:25+00
8069	3272	43	uncommon	\N	2025-11-29 12:10:25+00	2025-11-29 12:10:25+00
8070	3272	28	uncommon	\N	2025-11-29 12:10:25+00	2025-11-29 12:10:25+00
8071	3272	4	uncommon	\N	2025-11-29 12:10:25+00	2025-11-29 12:10:25+00
8221	3317	42	uncommon	\N	2025-11-29 14:58:57+00	2025-11-29 14:58:57+00
8222	3317	17	uncommon	\N	2025-11-29 14:58:57+00	2025-11-29 14:58:57+00
8223	3317	18	uncommon	\N	2025-11-29 14:58:57+00	2025-11-29 14:58:57+00
8224	3317	2	uncommon	\N	2025-11-29 14:58:57+00	2025-11-29 14:58:57+00
8225	3317	3	uncommon	\N	2025-11-29 14:58:57+00	2025-11-29 14:58:57+00
8226	3318	42	uncommon	\N	2025-11-29 14:58:57+00	2025-11-29 14:58:57+00
8227	3318	17	uncommon	\N	2025-11-29 14:58:57+00	2025-11-29 14:58:57+00
8228	3318	18	uncommon	\N	2025-11-29 14:58:57+00	2025-11-29 14:58:57+00
8229	3318	2	uncommon	\N	2025-11-29 14:58:57+00	2025-11-29 14:58:57+00
8230	3318	3	uncommon	\N	2025-11-29 14:58:57+00	2025-11-29 14:58:57+00
8231	3319	42	uncommon	\N	2025-11-29 14:58:57+00	2025-11-29 14:58:57+00
8232	3319	17	uncommon	\N	2025-11-29 14:58:57+00	2025-11-29 14:58:57+00
8233	3319	18	uncommon	\N	2025-11-29 14:58:57+00	2025-11-29 14:58:57+00
8234	3319	2	uncommon	\N	2025-11-29 14:58:57+00	2025-11-29 14:58:57+00
8235	3319	3	uncommon	\N	2025-11-29 14:58:57+00	2025-11-29 14:58:57+00
8236	3320	26	uncommon	\N	2025-11-29 15:01:51+00	2025-11-29 15:01:51+00
8237	3320	32	uncommon	\N	2025-11-29 15:01:51+00	2025-11-29 15:01:51+00
8238	3320	2	uncommon	\N	2025-11-29 15:01:51+00	2025-11-29 15:01:51+00
8239	3320	3	uncommon	\N	2025-11-29 15:01:51+00	2025-11-29 15:01:51+00
8240	3320	16	uncommon	\N	2025-11-29 15:01:51+00	2025-11-29 15:01:51+00
8241	3320	33	uncommon	\N	2025-11-29 15:01:51+00	2025-11-29 15:01:51+00
8242	3320	42	uncommon	\N	2025-11-29 15:01:51+00	2025-11-29 15:01:51+00
8243	3320	28	uncommon	\N	2025-11-29 15:01:51+00	2025-11-29 15:01:51+00
8244	3321	32	uncommon	\N	2025-11-29 15:01:51+00	2025-11-29 15:01:51+00
8245	3321	2	uncommon	\N	2025-11-29 15:01:51+00	2025-11-29 15:01:51+00
8246	3321	3	uncommon	\N	2025-11-29 15:01:51+00	2025-11-29 15:01:51+00
8247	3321	16	uncommon	\N	2025-11-29 15:01:51+00	2025-11-29 15:01:51+00
8248	3321	33	uncommon	\N	2025-11-29 15:01:51+00	2025-11-29 15:01:51+00
8249	3321	42	uncommon	\N	2025-11-29 15:01:51+00	2025-11-29 15:01:51+00
8250	3321	28	uncommon	\N	2025-11-29 15:01:51+00	2025-11-29 15:01:51+00
8314	3336	27	uncommon	\N	2025-11-29 15:19:19+00	2025-11-29 15:19:19+00
8315	3336	3	uncommon	\N	2025-11-29 15:19:19+00	2025-11-29 15:19:19+00
8316	3336	28	uncommon	\N	2025-11-29 15:19:19+00	2025-11-29 15:19:19+00
8317	3336	4	uncommon	\N	2025-11-29 15:19:19+00	2025-11-29 15:19:19+00
8318	3336	26	uncommon	\N	2025-11-29 15:19:19+00	2025-11-29 15:19:19+00
8319	3336	25	uncommon	\N	2025-11-29 15:19:19+00	2025-11-29 15:19:19+00
8320	3336	2	uncommon	\N	2025-11-29 15:19:19+00	2025-11-29 15:19:19+00
8321	3337	27	uncommon	\N	2025-11-29 15:19:19+00	2025-11-29 15:19:19+00
8322	3337	3	uncommon	\N	2025-11-29 15:19:19+00	2025-11-29 15:19:19+00
8323	3337	28	uncommon	\N	2025-11-29 15:19:19+00	2025-11-29 15:19:19+00
8324	3337	4	uncommon	\N	2025-11-29 15:19:19+00	2025-11-29 15:19:19+00
8325	3337	26	uncommon	\N	2025-11-29 15:19:19+00	2025-11-29 15:19:19+00
8326	3337	25	uncommon	\N	2025-11-29 15:19:19+00	2025-11-29 15:19:19+00
8327	3337	2	uncommon	\N	2025-11-29 15:19:19+00	2025-11-29 15:19:19+00
8328	3338	27	uncommon	\N	2025-11-29 15:19:19+00	2025-11-29 15:19:19+00
8329	3338	3	uncommon	\N	2025-11-29 15:19:19+00	2025-11-29 15:19:19+00
8330	3338	28	uncommon	\N	2025-11-29 15:19:19+00	2025-11-29 15:19:19+00
8331	3338	4	uncommon	\N	2025-11-29 15:19:19+00	2025-11-29 15:19:19+00
8332	3338	26	uncommon	\N	2025-11-29 15:19:19+00	2025-11-29 15:19:19+00
8333	3338	25	uncommon	\N	2025-11-29 15:19:19+00	2025-11-29 15:19:19+00
8334	3338	2	uncommon	\N	2025-11-29 15:19:19+00	2025-11-29 15:19:19+00
8697	3432	27	uncommon	\N	2025-12-04 18:47:23+00	2025-12-04 18:47:23+00
8698	3432	15	uncommon	\N	2025-12-04 18:47:23+00	2025-12-04 18:47:23+00
8699	3432	1	uncommon	\N	2025-12-04 18:47:23+00	2025-12-04 18:47:23+00
8700	3432	3	uncommon	\N	2025-12-04 18:47:23+00	2025-12-04 18:47:23+00
8701	3433	27	uncommon	\N	2025-12-04 18:47:23+00	2025-12-04 18:47:23+00
8702	3433	15	uncommon	\N	2025-12-04 18:47:23+00	2025-12-04 18:47:23+00
8703	3433	1	uncommon	\N	2025-12-04 18:47:23+00	2025-12-04 18:47:23+00
8704	3433	3	uncommon	\N	2025-12-04 18:47:23+00	2025-12-04 18:47:23+00
8705	3434	27	uncommon	\N	2025-12-04 18:47:23+00	2025-12-04 18:47:23+00
8706	3434	15	uncommon	\N	2025-12-04 18:47:23+00	2025-12-04 18:47:23+00
8707	3434	1	uncommon	\N	2025-12-04 18:47:23+00	2025-12-04 18:47:23+00
8708	3434	3	uncommon	\N	2025-12-04 18:47:23+00	2025-12-04 18:47:23+00
8709	3435	27	uncommon	\N	2025-12-04 18:47:23+00	2025-12-04 18:47:23+00
8710	3435	15	uncommon	\N	2025-12-04 18:47:23+00	2025-12-04 18:47:23+00
8711	3435	1	uncommon	\N	2025-12-04 18:47:23+00	2025-12-04 18:47:23+00
8712	3435	3	uncommon	\N	2025-12-04 18:47:23+00	2025-12-04 18:47:23+00
9280	3618	4	uncommon	\N	2025-12-14 17:51:31+00	2025-12-14 17:51:31+00
9281	3618	34	uncommon	\N	2025-12-14 17:51:31+00	2025-12-14 17:51:31+00
9282	3618	3	uncommon	\N	2025-12-14 17:51:31+00	2025-12-14 17:51:31+00
9283	3618	28	uncommon	\N	2025-12-14 17:51:31+00	2025-12-14 17:51:31+00
9284	3618	26	uncommon	\N	2025-12-14 17:51:31+00	2025-12-14 17:51:31+00
9285	3618	2	uncommon	\N	2025-12-14 17:51:31+00	2025-12-14 17:51:31+00
9286	3619	26	uncommon	\N	2025-12-14 17:51:31+00	2025-12-14 17:51:31+00
9287	3619	2	uncommon	\N	2025-12-14 17:51:31+00	2025-12-14 17:51:31+00
9288	3619	3	uncommon	\N	2025-12-14 17:51:31+00	2025-12-14 17:51:31+00
9289	3619	4	uncommon	\N	2025-12-14 17:51:31+00	2025-12-14 17:51:31+00
9290	3619	28	uncommon	\N	2025-12-14 17:51:31+00	2025-12-14 17:51:31+00
9291	3619	34	uncommon	\N	2025-12-14 17:51:31+00	2025-12-14 17:51:31+00
9292	3620	26	uncommon	\N	2025-12-14 17:51:31+00	2025-12-14 17:51:31+00
9293	3620	2	uncommon	\N	2025-12-14 17:51:31+00	2025-12-14 17:51:31+00
9294	3620	3	uncommon	\N	2025-12-14 17:51:31+00	2025-12-14 17:51:31+00
9295	3620	28	uncommon	\N	2025-12-14 17:51:31+00	2025-12-14 17:51:31+00
9296	3620	34	uncommon	\N	2025-12-14 17:51:31+00	2025-12-14 17:51:31+00
9297	3620	4	uncommon	\N	2025-12-14 17:51:31+00	2025-12-14 17:51:31+00
9376	3663	29	uncommon	\N	2025-12-18 20:41:49+00	2025-12-18 20:41:49+00
9377	3663	2	uncommon	\N	2025-12-18 20:41:49+00	2025-12-18 20:41:49+00
9378	3663	32	uncommon	\N	2025-12-18 20:41:49+00	2025-12-18 20:41:49+00
9379	3663	1	uncommon	\N	2025-12-18 20:41:49+00	2025-12-18 20:41:49+00
9380	3664	29	uncommon	\N	2025-12-18 20:41:49+00	2025-12-18 20:41:49+00
9381	3664	32	uncommon	\N	2025-12-18 20:41:49+00	2025-12-18 20:41:49+00
9382	3664	2	uncommon	\N	2025-12-18 20:41:49+00	2025-12-18 20:41:49+00
9383	3664	1	uncommon	\N	2025-12-18 20:41:49+00	2025-12-18 20:41:49+00
9384	3671	48	uncommon	\N	2025-12-18 23:39:55+00	2025-12-18 23:39:55+00
9385	3671	24	uncommon	\N	2025-12-18 23:39:55+00	2025-12-18 23:39:55+00
9386	3671	29	uncommon	\N	2025-12-18 23:39:55+00	2025-12-18 23:39:55+00
9387	3671	50	uncommon	\N	2025-12-18 23:39:55+00	2025-12-18 23:39:55+00
9388	3671	32	uncommon	\N	2025-12-18 23:39:55+00	2025-12-18 23:39:55+00
9389	3671	2	uncommon	\N	2025-12-18 23:39:55+00	2025-12-18 23:39:55+00
9390	3671	49	uncommon	\N	2025-12-18 23:39:55+00	2025-12-18 23:39:55+00
9391	3671	47	uncommon	\N	2025-12-18 23:39:55+00	2025-12-18 23:39:55+00
9392	3671	42	uncommon	\N	2025-12-18 23:39:55+00	2025-12-18 23:39:55+00
9393	3671	4	uncommon	\N	2025-12-18 23:39:55+00	2025-12-18 23:39:55+00
9394	3672	50	uncommon	\N	2025-12-18 23:39:55+00	2025-12-18 23:39:55+00
9395	3672	48	uncommon	\N	2025-12-18 23:39:55+00	2025-12-18 23:39:55+00
9396	3672	24	uncommon	\N	2025-12-18 23:39:55+00	2025-12-18 23:39:55+00
9397	3672	29	uncommon	\N	2025-12-18 23:39:55+00	2025-12-18 23:39:55+00
9398	3672	32	uncommon	\N	2025-12-18 23:39:55+00	2025-12-18 23:39:55+00
9399	3672	2	uncommon	\N	2025-12-18 23:39:55+00	2025-12-18 23:39:55+00
9400	3672	49	uncommon	\N	2025-12-18 23:39:55+00	2025-12-18 23:39:55+00
9401	3672	47	uncommon	\N	2025-12-18 23:39:55+00	2025-12-18 23:39:55+00
9402	3672	42	uncommon	\N	2025-12-18 23:39:55+00	2025-12-18 23:39:55+00
9403	3672	4	uncommon	\N	2025-12-18 23:39:55+00	2025-12-18 23:39:55+00
9404	3673	50	uncommon	\N	2025-12-18 23:39:55+00	2025-12-18 23:39:55+00
9405	3673	48	uncommon	\N	2025-12-18 23:39:55+00	2025-12-18 23:39:55+00
9406	3673	24	uncommon	\N	2025-12-18 23:39:55+00	2025-12-18 23:39:55+00
9407	3673	29	uncommon	\N	2025-12-18 23:39:55+00	2025-12-18 23:39:55+00
9408	3673	32	uncommon	\N	2025-12-18 23:39:55+00	2025-12-18 23:39:55+00
9409	3673	2	uncommon	\N	2025-12-18 23:39:55+00	2025-12-18 23:39:55+00
9410	3673	49	uncommon	\N	2025-12-18 23:39:55+00	2025-12-18 23:39:55+00
9411	3673	47	uncommon	\N	2025-12-18 23:39:55+00	2025-12-18 23:39:55+00
9412	3673	42	uncommon	\N	2025-12-18 23:39:55+00	2025-12-18 23:39:55+00
9413	3673	4	uncommon	\N	2025-12-18 23:39:55+00	2025-12-18 23:39:55+00
9432	3676	50	uncommon	\N	2025-12-19 00:17:45+00	2025-12-19 00:17:45+00
9433	3676	24	uncommon	\N	2025-12-19 00:17:45+00	2025-12-19 00:17:45+00
9434	3676	29	uncommon	\N	2025-12-19 00:17:45+00	2025-12-19 00:17:45+00
9435	3676	32	uncommon	\N	2025-12-19 00:17:45+00	2025-12-19 00:17:45+00
9436	3676	2	uncommon	\N	2025-12-19 00:17:45+00	2025-12-19 00:17:45+00
9437	3676	49	uncommon	\N	2025-12-19 00:17:45+00	2025-12-19 00:17:45+00
9438	3676	47	uncommon	\N	2025-12-19 00:17:45+00	2025-12-19 00:17:45+00
9439	3676	42	uncommon	\N	2025-12-19 00:17:45+00	2025-12-19 00:17:45+00
9440	3676	4	uncommon	\N	2025-12-19 00:17:45+00	2025-12-19 00:17:45+00
9441	3677	50	uncommon	\N	2025-12-19 00:17:45+00	2025-12-19 00:17:45+00
9442	3677	24	uncommon	\N	2025-12-19 00:17:45+00	2025-12-19 00:17:45+00
9443	3677	29	uncommon	\N	2025-12-19 00:17:45+00	2025-12-19 00:17:45+00
9444	3677	32	uncommon	\N	2025-12-19 00:17:45+00	2025-12-19 00:17:45+00
9445	3677	2	uncommon	\N	2025-12-19 00:17:45+00	2025-12-19 00:17:45+00
9446	3677	49	uncommon	\N	2025-12-19 00:17:45+00	2025-12-19 00:17:45+00
9447	3677	47	uncommon	\N	2025-12-19 00:17:45+00	2025-12-19 00:17:45+00
9448	3677	42	uncommon	\N	2025-12-19 00:17:45+00	2025-12-19 00:17:45+00
9449	3677	4	uncommon	\N	2025-12-19 00:17:45+00	2025-12-19 00:17:45+00
9546	3696	26	uncommon	\N	2025-12-19 23:23:05+00	2025-12-19 23:23:05+00
9547	3696	24	uncommon	\N	2025-12-19 23:23:05+00	2025-12-19 23:23:05+00
9548	3696	20	uncommon	\N	2025-12-19 23:23:05+00	2025-12-19 23:23:05+00
9549	3696	32	uncommon	\N	2025-12-19 23:23:05+00	2025-12-19 23:23:05+00
9550	3696	25	uncommon	\N	2025-12-19 23:23:05+00	2025-12-19 23:23:05+00
9551	3696	2	uncommon	\N	2025-12-19 23:23:05+00	2025-12-19 23:23:05+00
9552	3696	1	uncommon	\N	2025-12-19 23:23:05+00	2025-12-19 23:23:05+00
9553	3696	4	uncommon	\N	2025-12-19 23:23:05+00	2025-12-19 23:23:05+00
9554	3697	26	uncommon	\N	2025-12-19 23:23:05+00	2025-12-19 23:23:05+00
9555	3697	24	uncommon	\N	2025-12-19 23:23:05+00	2025-12-19 23:23:05+00
9556	3697	20	uncommon	\N	2025-12-19 23:23:05+00	2025-12-19 23:23:05+00
9557	3697	32	uncommon	\N	2025-12-19 23:23:05+00	2025-12-19 23:23:05+00
9558	3697	25	uncommon	\N	2025-12-19 23:23:05+00	2025-12-19 23:23:05+00
9559	3697	2	uncommon	\N	2025-12-19 23:23:05+00	2025-12-19 23:23:05+00
9560	3697	1	uncommon	\N	2025-12-19 23:23:05+00	2025-12-19 23:23:05+00
9561	3697	4	uncommon	\N	2025-12-19 23:23:05+00	2025-12-19 23:23:05+00
9562	3698	26	uncommon	\N	2025-12-19 23:23:05+00	2025-12-19 23:23:05+00
9563	3698	24	uncommon	\N	2025-12-19 23:23:05+00	2025-12-19 23:23:05+00
9564	3698	20	uncommon	\N	2025-12-19 23:23:05+00	2025-12-19 23:23:05+00
9565	3698	32	uncommon	\N	2025-12-19 23:23:05+00	2025-12-19 23:23:05+00
9566	3698	25	uncommon	\N	2025-12-19 23:23:05+00	2025-12-19 23:23:05+00
9567	3698	2	uncommon	\N	2025-12-19 23:23:05+00	2025-12-19 23:23:05+00
9568	3698	1	uncommon	\N	2025-12-19 23:23:05+00	2025-12-19 23:23:05+00
9569	3698	4	uncommon	\N	2025-12-19 23:23:05+00	2025-12-19 23:23:05+00
9570	3699	26	uncommon	\N	2025-12-19 23:23:05+00	2025-12-19 23:23:05+00
9571	3699	24	uncommon	\N	2025-12-19 23:23:05+00	2025-12-19 23:23:05+00
9572	3699	20	uncommon	\N	2025-12-19 23:23:05+00	2025-12-19 23:23:05+00
9573	3699	32	uncommon	\N	2025-12-19 23:23:05+00	2025-12-19 23:23:05+00
9574	3699	25	uncommon	\N	2025-12-19 23:23:05+00	2025-12-19 23:23:05+00
9575	3699	2	uncommon	\N	2025-12-19 23:23:05+00	2025-12-19 23:23:05+00
9576	3699	1	uncommon	\N	2025-12-19 23:23:05+00	2025-12-19 23:23:05+00
9577	3699	4	uncommon	\N	2025-12-19 23:23:05+00	2025-12-19 23:23:05+00
9578	3700	26	uncommon	\N	2025-12-19 23:23:05+00	2025-12-19 23:23:05+00
9579	3700	24	uncommon	\N	2025-12-19 23:23:05+00	2025-12-19 23:23:05+00
9580	3700	20	uncommon	\N	2025-12-19 23:23:05+00	2025-12-19 23:23:05+00
9581	3700	32	uncommon	\N	2025-12-19 23:23:05+00	2025-12-19 23:23:05+00
9582	3700	25	uncommon	\N	2025-12-19 23:23:05+00	2025-12-19 23:23:05+00
9583	3700	2	uncommon	\N	2025-12-19 23:23:05+00	2025-12-19 23:23:05+00
9584	3700	1	uncommon	\N	2025-12-19 23:23:05+00	2025-12-19 23:23:05+00
9585	3700	4	uncommon	\N	2025-12-19 23:23:05+00	2025-12-19 23:23:05+00
9586	3701	26	uncommon	\N	2025-12-19 23:23:05+00	2025-12-19 23:23:05+00
9587	3701	24	uncommon	\N	2025-12-19 23:23:05+00	2025-12-19 23:23:05+00
9588	3701	20	uncommon	\N	2025-12-19 23:23:05+00	2025-12-19 23:23:05+00
9589	3701	32	uncommon	\N	2025-12-19 23:23:05+00	2025-12-19 23:23:05+00
9590	3701	25	uncommon	\N	2025-12-19 23:23:05+00	2025-12-19 23:23:05+00
9591	3701	2	uncommon	\N	2025-12-19 23:23:05+00	2025-12-19 23:23:05+00
9592	3701	1	uncommon	\N	2025-12-19 23:23:05+00	2025-12-19 23:23:05+00
9593	3701	4	uncommon	\N	2025-12-19 23:23:05+00	2025-12-19 23:23:05+00
9594	3706	25	uncommon	\N	2025-12-19 23:59:41+00	2025-12-19 23:59:41+00
9595	3706	32	uncommon	\N	2025-12-19 23:59:41+00	2025-12-19 23:59:41+00
9596	3706	2	uncommon	\N	2025-12-19 23:59:41+00	2025-12-19 23:59:41+00
9597	3706	22	uncommon	\N	2025-12-19 23:59:41+00	2025-12-19 23:59:41+00
9598	3706	3	uncommon	\N	2025-12-19 23:59:41+00	2025-12-19 23:59:41+00
9599	3706	46	uncommon	\N	2025-12-19 23:59:41+00	2025-12-19 23:59:41+00
9600	3706	16	uncommon	\N	2025-12-19 23:59:41+00	2025-12-19 23:59:41+00
9601	3706	4	uncommon	\N	2025-12-19 23:59:41+00	2025-12-19 23:59:41+00
9602	3707	46	uncommon	\N	2025-12-19 23:59:41+00	2025-12-19 23:59:41+00
9603	3707	32	uncommon	\N	2025-12-19 23:59:41+00	2025-12-19 23:59:41+00
9604	3707	2	uncommon	\N	2025-12-19 23:59:41+00	2025-12-19 23:59:41+00
9605	3707	25	uncommon	\N	2025-12-19 23:59:41+00	2025-12-19 23:59:41+00
9606	3707	22	uncommon	\N	2025-12-19 23:59:41+00	2025-12-19 23:59:41+00
9607	3707	3	uncommon	\N	2025-12-19 23:59:41+00	2025-12-19 23:59:41+00
9608	3707	16	uncommon	\N	2025-12-19 23:59:41+00	2025-12-19 23:59:41+00
9609	3707	4	uncommon	\N	2025-12-19 23:59:41+00	2025-12-19 23:59:41+00
9610	3708	46	uncommon	\N	2025-12-19 23:59:41+00	2025-12-19 23:59:41+00
9611	3708	25	uncommon	\N	2025-12-19 23:59:41+00	2025-12-19 23:59:41+00
9612	3708	32	uncommon	\N	2025-12-19 23:59:41+00	2025-12-19 23:59:41+00
9613	3708	2	uncommon	\N	2025-12-19 23:59:41+00	2025-12-19 23:59:41+00
9614	3708	22	uncommon	\N	2025-12-19 23:59:41+00	2025-12-19 23:59:41+00
9615	3708	3	uncommon	\N	2025-12-19 23:59:41+00	2025-12-19 23:59:41+00
9616	3708	16	uncommon	\N	2025-12-19 23:59:41+00	2025-12-19 23:59:41+00
9617	3708	4	uncommon	\N	2025-12-19 23:59:41+00	2025-12-19 23:59:41+00
9618	3715	51	uncommon	\N	2025-12-21 01:02:09+00	2025-12-21 01:02:09+00
9619	3715	29	uncommon	\N	2025-12-21 01:02:09+00	2025-12-21 01:02:09+00
9620	3715	44	uncommon	\N	2025-12-21 01:02:09+00	2025-12-21 01:02:09+00
9621	3715	32	uncommon	\N	2025-12-21 01:02:09+00	2025-12-21 01:02:09+00
9622	3715	20	uncommon	\N	2025-12-21 01:02:09+00	2025-12-21 01:02:09+00
9623	3715	2	uncommon	\N	2025-12-21 01:02:09+00	2025-12-21 01:02:09+00
9624	3715	3	uncommon	\N	2025-12-21 01:02:09+00	2025-12-21 01:02:09+00
9625	3715	4	uncommon	\N	2025-12-21 01:02:09+00	2025-12-21 01:02:09+00
9626	3716	51	uncommon	\N	2025-12-21 01:02:09+00	2025-12-21 01:02:09+00
9627	3716	29	uncommon	\N	2025-12-21 01:02:09+00	2025-12-21 01:02:09+00
9628	3716	44	uncommon	\N	2025-12-21 01:02:09+00	2025-12-21 01:02:09+00
9629	3716	20	uncommon	\N	2025-12-21 01:02:09+00	2025-12-21 01:02:09+00
9630	3716	32	uncommon	\N	2025-12-21 01:02:09+00	2025-12-21 01:02:09+00
9631	3716	2	uncommon	\N	2025-12-21 01:02:09+00	2025-12-21 01:02:09+00
9632	3716	3	uncommon	\N	2025-12-21 01:02:09+00	2025-12-21 01:02:09+00
9633	3716	4	uncommon	\N	2025-12-21 01:02:09+00	2025-12-21 01:02:09+00
9634	3717	51	uncommon	\N	2025-12-21 01:02:09+00	2025-12-21 01:02:09+00
9635	3717	29	uncommon	\N	2025-12-21 01:02:09+00	2025-12-21 01:02:09+00
9636	3717	44	uncommon	\N	2025-12-21 01:02:09+00	2025-12-21 01:02:09+00
9637	3717	20	uncommon	\N	2025-12-21 01:02:09+00	2025-12-21 01:02:09+00
9638	3717	32	uncommon	\N	2025-12-21 01:02:09+00	2025-12-21 01:02:09+00
9639	3717	2	uncommon	\N	2025-12-21 01:02:09+00	2025-12-21 01:02:09+00
9640	3717	3	uncommon	\N	2025-12-21 01:02:09+00	2025-12-21 01:02:09+00
9641	3717	4	uncommon	\N	2025-12-21 01:02:09+00	2025-12-21 01:02:09+00
11294	4169	29	uncommon	\N	2026-01-16 23:34:16+00	2026-01-16 23:34:16+00
11295	4169	17	uncommon	\N	2026-01-16 23:34:16+00	2026-01-16 23:34:16+00
11296	4169	18	uncommon	\N	2026-01-16 23:34:16+00	2026-01-16 23:34:16+00
11297	4169	27	uncommon	\N	2026-01-16 23:34:16+00	2026-01-16 23:34:16+00
11298	4169	36	uncommon	\N	2026-01-16 23:34:16+00	2026-01-16 23:34:16+00
11299	4169	44	uncommon	\N	2026-01-16 23:34:16+00	2026-01-16 23:34:16+00
11300	4169	3	uncommon	\N	2026-01-16 23:34:16+00	2026-01-16 23:34:16+00
11301	4169	37	uncommon	\N	2026-01-16 23:34:16+00	2026-01-16 23:34:16+00
11302	4170	29	uncommon	\N	2026-01-16 23:34:16+00	2026-01-16 23:34:16+00
11303	4170	17	uncommon	\N	2026-01-16 23:34:16+00	2026-01-16 23:34:16+00
11304	4170	18	uncommon	\N	2026-01-16 23:34:16+00	2026-01-16 23:34:16+00
11305	4170	36	uncommon	\N	2026-01-16 23:34:16+00	2026-01-16 23:34:16+00
11306	4170	27	uncommon	\N	2026-01-16 23:34:16+00	2026-01-16 23:34:16+00
11307	4170	44	uncommon	\N	2026-01-16 23:34:16+00	2026-01-16 23:34:16+00
11308	4170	3	uncommon	\N	2026-01-16 23:34:16+00	2026-01-16 23:34:16+00
11309	4170	37	uncommon	\N	2026-01-16 23:34:16+00	2026-01-16 23:34:16+00
11310	4171	17	uncommon	\N	2026-01-16 23:34:16+00	2026-01-16 23:34:16+00
11311	4171	29	uncommon	\N	2026-01-16 23:34:16+00	2026-01-16 23:34:16+00
11312	4171	18	uncommon	\N	2026-01-16 23:34:16+00	2026-01-16 23:34:16+00
11313	4171	36	uncommon	\N	2026-01-16 23:34:16+00	2026-01-16 23:34:16+00
11314	4171	27	uncommon	\N	2026-01-16 23:34:16+00	2026-01-16 23:34:16+00
11315	4171	44	uncommon	\N	2026-01-16 23:34:16+00	2026-01-16 23:34:16+00
11316	4171	3	uncommon	\N	2026-01-16 23:34:16+00	2026-01-16 23:34:16+00
11317	4171	37	uncommon	\N	2026-01-16 23:34:16+00	2026-01-16 23:34:16+00
11888	4324	26	uncommon	\N	2026-02-05 19:30:37+00	2026-02-05 19:30:37+00
11889	4324	40	uncommon	\N	2026-02-05 19:30:37+00	2026-02-05 19:30:37+00
11890	4324	17	uncommon	\N	2026-02-05 19:30:37+00	2026-02-05 19:30:37+00
11891	4324	39	uncommon	\N	2026-02-05 19:30:37+00	2026-02-05 19:30:37+00
11892	4324	32	uncommon	\N	2026-02-05 19:30:37+00	2026-02-05 19:30:37+00
11893	4324	2	uncommon	\N	2026-02-05 19:30:37+00	2026-02-05 19:30:37+00
11894	4324	38	uncommon	\N	2026-02-05 19:30:37+00	2026-02-05 19:30:37+00
11895	4324	3	uncommon	\N	2026-02-05 19:30:37+00	2026-02-05 19:30:37+00
11896	4324	28	uncommon	\N	2026-02-05 19:30:37+00	2026-02-05 19:30:37+00
11897	4324	4	uncommon	\N	2026-02-05 19:30:37+00	2026-02-05 19:30:37+00
11898	4325	26	uncommon	\N	2026-02-05 19:30:37+00	2026-02-05 19:30:37+00
11899	4325	40	uncommon	\N	2026-02-05 19:30:37+00	2026-02-05 19:30:37+00
11900	4325	17	uncommon	\N	2026-02-05 19:30:37+00	2026-02-05 19:30:37+00
11901	4325	39	uncommon	\N	2026-02-05 19:30:37+00	2026-02-05 19:30:37+00
11902	4325	32	uncommon	\N	2026-02-05 19:30:37+00	2026-02-05 19:30:37+00
11903	4325	2	uncommon	\N	2026-02-05 19:30:37+00	2026-02-05 19:30:37+00
11904	4325	38	uncommon	\N	2026-02-05 19:30:37+00	2026-02-05 19:30:37+00
11905	4325	3	uncommon	\N	2026-02-05 19:30:37+00	2026-02-05 19:30:37+00
11906	4325	28	uncommon	\N	2026-02-05 19:30:37+00	2026-02-05 19:30:37+00
11907	4325	4	uncommon	\N	2026-02-05 19:30:37+00	2026-02-05 19:30:37+00
11908	4326	40	uncommon	\N	2026-02-05 19:30:37+00	2026-02-05 19:30:37+00
11909	4326	17	uncommon	\N	2026-02-05 19:30:37+00	2026-02-05 19:30:37+00
11910	4326	39	uncommon	\N	2026-02-05 19:30:37+00	2026-02-05 19:30:37+00
11911	4326	32	uncommon	\N	2026-02-05 19:30:37+00	2026-02-05 19:30:37+00
11912	4326	2	uncommon	\N	2026-02-05 19:30:37+00	2026-02-05 19:30:37+00
11913	4326	38	uncommon	\N	2026-02-05 19:30:37+00	2026-02-05 19:30:37+00
11914	4326	3	uncommon	\N	2026-02-05 19:30:37+00	2026-02-05 19:30:37+00
11915	4326	28	uncommon	\N	2026-02-05 19:30:37+00	2026-02-05 19:30:37+00
11916	4326	4	uncommon	\N	2026-02-05 19:30:37+00	2026-02-05 19:30:37+00
11917	4327	26	uncommon	\N	2026-02-05 19:30:37+00	2026-02-05 19:30:37+00
11918	4327	40	uncommon	\N	2026-02-05 19:30:37+00	2026-02-05 19:30:37+00
11919	4327	17	uncommon	\N	2026-02-05 19:30:37+00	2026-02-05 19:30:37+00
11920	4327	39	uncommon	\N	2026-02-05 19:30:37+00	2026-02-05 19:30:37+00
11921	4327	32	uncommon	\N	2026-02-05 19:30:37+00	2026-02-05 19:30:37+00
11922	4327	2	uncommon	\N	2026-02-05 19:30:37+00	2026-02-05 19:30:37+00
11923	4327	38	uncommon	\N	2026-02-05 19:30:37+00	2026-02-05 19:30:37+00
11924	4327	3	uncommon	\N	2026-02-05 19:30:37+00	2026-02-05 19:30:37+00
11925	4327	28	uncommon	\N	2026-02-05 19:30:37+00	2026-02-05 19:30:37+00
11926	4327	4	uncommon	\N	2026-02-05 19:30:37+00	2026-02-05 19:30:37+00
12086	4365	17	uncommon	\N	2026-02-06 00:22:09+00	2026-02-06 00:22:09+00
12087	4365	1	uncommon	\N	2026-02-06 00:22:09+00	2026-02-06 00:22:09+00
12088	4365	3	uncommon	\N	2026-02-06 00:22:09+00	2026-02-06 00:22:09+00
12089	4366	17	uncommon	\N	2026-02-06 00:22:09+00	2026-02-06 00:22:09+00
12090	4366	1	uncommon	\N	2026-02-06 00:22:09+00	2026-02-06 00:22:09+00
12091	4366	3	uncommon	\N	2026-02-06 00:22:09+00	2026-02-06 00:22:09+00
12092	4367	17	uncommon	\N	2026-02-06 00:22:09+00	2026-02-06 00:22:09+00
12093	4367	1	uncommon	\N	2026-02-06 00:22:09+00	2026-02-06 00:22:09+00
12094	4367	3	uncommon	\N	2026-02-06 00:22:09+00	2026-02-06 00:22:09+00
12095	4368	27	uncommon	\N	2026-02-06 00:22:55+00	2026-02-06 00:22:55+00
12096	4368	2	uncommon	\N	2026-02-06 00:22:55+00	2026-02-06 00:22:55+00
12097	4368	14	uncommon	\N	2026-02-06 00:22:55+00	2026-02-06 00:22:55+00
12098	4368	1	uncommon	\N	2026-02-06 00:22:55+00	2026-02-06 00:22:55+00
12099	4368	3	uncommon	\N	2026-02-06 00:22:55+00	2026-02-06 00:22:55+00
12100	4369	27	uncommon	\N	2026-02-06 00:22:55+00	2026-02-06 00:22:55+00
12101	4369	2	uncommon	\N	2026-02-06 00:22:55+00	2026-02-06 00:22:55+00
12102	4369	14	uncommon	\N	2026-02-06 00:22:55+00	2026-02-06 00:22:55+00
12103	4369	1	uncommon	\N	2026-02-06 00:22:55+00	2026-02-06 00:22:55+00
12104	4369	3	uncommon	\N	2026-02-06 00:22:55+00	2026-02-06 00:22:55+00
12105	4370	2	uncommon	\N	2026-02-06 00:23:53+00	2026-02-06 00:23:53+00
12106	4370	1	uncommon	\N	2026-02-06 00:23:53+00	2026-02-06 00:23:53+00
12107	4370	3	uncommon	\N	2026-02-06 00:23:53+00	2026-02-06 00:23:53+00
12108	4370	4	uncommon	\N	2026-02-06 00:23:53+00	2026-02-06 00:23:53+00
12109	4371	2	uncommon	\N	2026-02-06 00:23:53+00	2026-02-06 00:23:53+00
12110	4371	1	uncommon	\N	2026-02-06 00:23:53+00	2026-02-06 00:23:53+00
12111	4371	3	uncommon	\N	2026-02-06 00:23:53+00	2026-02-06 00:23:53+00
12112	4371	4	uncommon	\N	2026-02-06 00:23:53+00	2026-02-06 00:23:53+00
12113	4372	2	uncommon	\N	2026-02-06 00:23:53+00	2026-02-06 00:23:53+00
12114	4372	1	uncommon	\N	2026-02-06 00:23:53+00	2026-02-06 00:23:53+00
12115	4372	3	uncommon	\N	2026-02-06 00:23:53+00	2026-02-06 00:23:53+00
12116	4372	4	uncommon	\N	2026-02-06 00:23:53+00	2026-02-06 00:23:53+00
12117	4373	2	uncommon	\N	2026-02-06 00:23:53+00	2026-02-06 00:23:53+00
12118	4373	1	uncommon	\N	2026-02-06 00:23:53+00	2026-02-06 00:23:53+00
12119	4373	3	uncommon	\N	2026-02-06 00:23:53+00	2026-02-06 00:23:53+00
12120	4373	4	uncommon	\N	2026-02-06 00:23:53+00	2026-02-06 00:23:53+00
12121	4374	2	uncommon	\N	2026-02-06 00:23:53+00	2026-02-06 00:23:53+00
12122	4374	3	uncommon	\N	2026-02-06 00:23:53+00	2026-02-06 00:23:53+00
12123	4374	4	uncommon	\N	2026-02-06 00:23:53+00	2026-02-06 00:23:53+00
12124	4375	2	uncommon	\N	2026-02-06 00:23:53+00	2026-02-06 00:23:53+00
12125	4375	3	uncommon	\N	2026-02-06 00:23:53+00	2026-02-06 00:23:53+00
12126	4375	4	uncommon	\N	2026-02-06 00:23:53+00	2026-02-06 00:23:53+00
12127	4376	2	uncommon	\N	2026-02-06 00:23:53+00	2026-02-06 00:23:53+00
12128	4376	3	uncommon	\N	2026-02-06 00:23:53+00	2026-02-06 00:23:53+00
12129	4376	4	uncommon	\N	2026-02-06 00:23:53+00	2026-02-06 00:23:53+00
12146	4381	1	uncommon	\N	2026-02-06 00:24:33+00	2026-02-06 00:24:33+00
12147	4381	3	uncommon	\N	2026-02-06 00:24:33+00	2026-02-06 00:24:33+00
12148	4381	4	uncommon	\N	2026-02-06 00:24:33+00	2026-02-06 00:24:33+00
12149	4382	1	uncommon	\N	2026-02-06 00:24:33+00	2026-02-06 00:24:33+00
12150	4382	3	uncommon	\N	2026-02-06 00:24:33+00	2026-02-06 00:24:33+00
12151	4382	4	uncommon	\N	2026-02-06 00:24:33+00	2026-02-06 00:24:33+00
12152	4383	1	uncommon	\N	2026-02-06 00:24:33+00	2026-02-06 00:24:33+00
12153	4383	3	uncommon	\N	2026-02-06 00:24:33+00	2026-02-06 00:24:33+00
12154	4383	4	uncommon	\N	2026-02-06 00:24:33+00	2026-02-06 00:24:33+00
12155	4384	3	uncommon	\N	2026-02-06 00:24:33+00	2026-02-06 00:24:33+00
12156	4384	4	uncommon	\N	2026-02-06 00:24:33+00	2026-02-06 00:24:33+00
12157	4385	3	uncommon	\N	2026-02-06 00:24:33+00	2026-02-06 00:24:33+00
12158	4385	4	uncommon	\N	2026-02-06 00:24:33+00	2026-02-06 00:24:33+00
12159	4386	2	uncommon	\N	2026-02-06 00:24:33+00	2026-02-06 00:24:33+00
12160	4386	3	uncommon	\N	2026-02-06 00:24:33+00	2026-02-06 00:24:33+00
12161	4386	4	uncommon	\N	2026-02-06 00:24:33+00	2026-02-06 00:24:33+00
12162	4387	29	uncommon	\N	2026-02-06 00:24:51+00	2026-02-06 00:24:51+00
12163	4387	2	uncommon	\N	2026-02-06 00:24:51+00	2026-02-06 00:24:51+00
12164	4387	14	uncommon	\N	2026-02-06 00:24:51+00	2026-02-06 00:24:51+00
12165	4387	21	uncommon	\N	2026-02-06 00:24:51+00	2026-02-06 00:24:51+00
12166	4387	1	uncommon	\N	2026-02-06 00:24:51+00	2026-02-06 00:24:51+00
12167	4387	3	uncommon	\N	2026-02-06 00:24:51+00	2026-02-06 00:24:51+00
12168	4387	30	uncommon	\N	2026-02-06 00:24:51+00	2026-02-06 00:24:51+00
12169	4387	28	uncommon	\N	2026-02-06 00:24:51+00	2026-02-06 00:24:51+00
12170	4387	4	uncommon	\N	2026-02-06 00:24:51+00	2026-02-06 00:24:51+00
12171	4388	29	uncommon	\N	2026-02-06 00:24:51+00	2026-02-06 00:24:51+00
12172	4388	2	uncommon	\N	2026-02-06 00:24:51+00	2026-02-06 00:24:51+00
12173	4388	14	uncommon	\N	2026-02-06 00:24:51+00	2026-02-06 00:24:51+00
12174	4388	21	uncommon	\N	2026-02-06 00:24:51+00	2026-02-06 00:24:51+00
12175	4388	1	uncommon	\N	2026-02-06 00:24:51+00	2026-02-06 00:24:51+00
12176	4388	3	uncommon	\N	2026-02-06 00:24:51+00	2026-02-06 00:24:51+00
12177	4388	30	uncommon	\N	2026-02-06 00:24:51+00	2026-02-06 00:24:51+00
12178	4388	28	uncommon	\N	2026-02-06 00:24:51+00	2026-02-06 00:24:51+00
12179	4388	4	uncommon	\N	2026-02-06 00:24:51+00	2026-02-06 00:24:51+00
12180	4389	29	uncommon	\N	2026-02-06 00:24:51+00	2026-02-06 00:24:51+00
12181	4389	2	uncommon	\N	2026-02-06 00:24:51+00	2026-02-06 00:24:51+00
12182	4389	14	uncommon	\N	2026-02-06 00:24:51+00	2026-02-06 00:24:51+00
12183	4389	21	uncommon	\N	2026-02-06 00:24:51+00	2026-02-06 00:24:51+00
12184	4389	1	uncommon	\N	2026-02-06 00:24:51+00	2026-02-06 00:24:51+00
12185	4389	3	uncommon	\N	2026-02-06 00:24:51+00	2026-02-06 00:24:51+00
12186	4389	30	uncommon	\N	2026-02-06 00:24:51+00	2026-02-06 00:24:51+00
12187	4389	28	uncommon	\N	2026-02-06 00:24:51+00	2026-02-06 00:24:51+00
12188	4389	4	uncommon	\N	2026-02-06 00:24:51+00	2026-02-06 00:24:51+00
12199	4400	27	uncommon	\N	2026-02-06 00:26:49+00	2026-02-06 00:26:49+00
12200	4400	1	uncommon	\N	2026-02-06 00:26:49+00	2026-02-06 00:26:49+00
12201	4400	3	uncommon	\N	2026-02-06 00:26:49+00	2026-02-06 00:26:49+00
12202	4400	4	uncommon	\N	2026-02-06 00:26:49+00	2026-02-06 00:26:49+00
12203	4401	27	uncommon	\N	2026-02-06 00:26:49+00	2026-02-06 00:26:49+00
12204	4401	1	uncommon	\N	2026-02-06 00:26:49+00	2026-02-06 00:26:49+00
12205	4401	3	uncommon	\N	2026-02-06 00:26:49+00	2026-02-06 00:26:49+00
12206	4401	4	uncommon	\N	2026-02-06 00:26:49+00	2026-02-06 00:26:49+00
12207	4402	27	uncommon	\N	2026-02-06 00:26:49+00	2026-02-06 00:26:49+00
12208	4402	1	uncommon	\N	2026-02-06 00:26:49+00	2026-02-06 00:26:49+00
12209	4402	3	uncommon	\N	2026-02-06 00:26:49+00	2026-02-06 00:26:49+00
12210	4402	4	uncommon	\N	2026-02-06 00:26:49+00	2026-02-06 00:26:49+00
12211	4403	27	uncommon	\N	2026-02-06 00:26:49+00	2026-02-06 00:26:49+00
12212	4403	2	uncommon	\N	2026-02-06 00:26:49+00	2026-02-06 00:26:49+00
12213	4403	3	uncommon	\N	2026-02-06 00:26:49+00	2026-02-06 00:26:49+00
12214	4403	4	uncommon	\N	2026-02-06 00:26:49+00	2026-02-06 00:26:49+00
12215	4404	27	uncommon	\N	2026-02-06 00:26:49+00	2026-02-06 00:26:49+00
12216	4404	2	uncommon	\N	2026-02-06 00:26:49+00	2026-02-06 00:26:49+00
12217	4404	3	uncommon	\N	2026-02-06 00:26:49+00	2026-02-06 00:26:49+00
12218	4404	4	uncommon	\N	2026-02-06 00:26:49+00	2026-02-06 00:26:49+00
12219	4405	27	uncommon	\N	2026-02-06 00:26:49+00	2026-02-06 00:26:49+00
12220	4405	2	uncommon	\N	2026-02-06 00:26:49+00	2026-02-06 00:26:49+00
12221	4405	3	uncommon	\N	2026-02-06 00:26:49+00	2026-02-06 00:26:49+00
12222	4405	4	uncommon	\N	2026-02-06 00:26:49+00	2026-02-06 00:26:49+00
12223	4406	24	uncommon	\N	2026-02-06 00:27:10+00	2026-02-06 00:27:10+00
12224	4406	32	uncommon	\N	2026-02-06 00:27:10+00	2026-02-06 00:27:10+00
12225	4406	2	uncommon	\N	2026-02-06 00:27:10+00	2026-02-06 00:27:10+00
12226	4406	1	uncommon	\N	2026-02-06 00:27:10+00	2026-02-06 00:27:10+00
12227	4406	3	uncommon	\N	2026-02-06 00:27:10+00	2026-02-06 00:27:10+00
12228	4407	24	uncommon	\N	2026-02-06 00:27:10+00	2026-02-06 00:27:10+00
12229	4407	32	uncommon	\N	2026-02-06 00:27:10+00	2026-02-06 00:27:10+00
12230	4407	2	uncommon	\N	2026-02-06 00:27:10+00	2026-02-06 00:27:10+00
12231	4407	1	uncommon	\N	2026-02-06 00:27:10+00	2026-02-06 00:27:10+00
12232	4407	3	uncommon	\N	2026-02-06 00:27:10+00	2026-02-06 00:27:10+00
12233	4408	24	uncommon	\N	2026-02-06 00:27:10+00	2026-02-06 00:27:10+00
12234	4408	32	uncommon	\N	2026-02-06 00:27:10+00	2026-02-06 00:27:10+00
12235	4408	2	uncommon	\N	2026-02-06 00:27:10+00	2026-02-06 00:27:10+00
12236	4408	1	uncommon	\N	2026-02-06 00:27:10+00	2026-02-06 00:27:10+00
12237	4408	3	uncommon	\N	2026-02-06 00:27:10+00	2026-02-06 00:27:10+00
12238	4409	24	uncommon	\N	2026-02-06 00:27:10+00	2026-02-06 00:27:10+00
12239	4409	32	uncommon	\N	2026-02-06 00:27:10+00	2026-02-06 00:27:10+00
12240	4409	2	uncommon	\N	2026-02-06 00:27:10+00	2026-02-06 00:27:10+00
12241	4409	1	uncommon	\N	2026-02-06 00:27:10+00	2026-02-06 00:27:10+00
12242	4409	3	uncommon	\N	2026-02-06 00:27:10+00	2026-02-06 00:27:10+00
12243	4410	24	uncommon	\N	2026-02-06 00:27:10+00	2026-02-06 00:27:10+00
12244	4410	32	uncommon	\N	2026-02-06 00:27:10+00	2026-02-06 00:27:10+00
12245	4410	2	uncommon	\N	2026-02-06 00:27:10+00	2026-02-06 00:27:10+00
12246	4410	1	uncommon	\N	2026-02-06 00:27:10+00	2026-02-06 00:27:10+00
12247	4410	3	uncommon	\N	2026-02-06 00:27:10+00	2026-02-06 00:27:10+00
12248	4411	24	uncommon	\N	2026-02-06 00:27:10+00	2026-02-06 00:27:10+00
12249	4411	32	uncommon	\N	2026-02-06 00:27:10+00	2026-02-06 00:27:10+00
12250	4411	2	uncommon	\N	2026-02-06 00:27:10+00	2026-02-06 00:27:10+00
12251	4411	1	uncommon	\N	2026-02-06 00:27:10+00	2026-02-06 00:27:10+00
12252	4411	3	uncommon	\N	2026-02-06 00:27:10+00	2026-02-06 00:27:10+00
12253	4412	24	uncommon	\N	2026-02-06 00:27:10+00	2026-02-06 00:27:10+00
12254	4412	32	uncommon	\N	2026-02-06 00:27:10+00	2026-02-06 00:27:10+00
12255	4412	2	uncommon	\N	2026-02-06 00:27:10+00	2026-02-06 00:27:10+00
12256	4412	1	uncommon	\N	2026-02-06 00:27:10+00	2026-02-06 00:27:10+00
12257	4412	3	uncommon	\N	2026-02-06 00:27:10+00	2026-02-06 00:27:10+00
12258	4413	45	uncommon	\N	2026-02-06 00:27:33+00	2026-02-06 00:27:33+00
12259	4414	45	uncommon	\N	2026-02-06 00:27:33+00	2026-02-06 00:27:33+00
12260	4415	2	uncommon	\N	2026-02-06 00:27:51+00	2026-02-06 00:27:51+00
12261	4415	1	uncommon	\N	2026-02-06 00:27:51+00	2026-02-06 00:27:51+00
12262	4415	3	uncommon	\N	2026-02-06 00:27:51+00	2026-02-06 00:27:51+00
12263	4415	28	uncommon	\N	2026-02-06 00:27:51+00	2026-02-06 00:27:51+00
12264	4415	4	uncommon	\N	2026-02-06 00:27:51+00	2026-02-06 00:27:51+00
12265	4416	2	uncommon	\N	2026-02-06 00:27:51+00	2026-02-06 00:27:51+00
12266	4416	1	uncommon	\N	2026-02-06 00:27:51+00	2026-02-06 00:27:51+00
12267	4416	3	uncommon	\N	2026-02-06 00:27:51+00	2026-02-06 00:27:51+00
12268	4416	28	uncommon	\N	2026-02-06 00:27:51+00	2026-02-06 00:27:51+00
12269	4416	4	uncommon	\N	2026-02-06 00:27:51+00	2026-02-06 00:27:51+00
12270	4417	2	uncommon	\N	2026-02-06 00:27:51+00	2026-02-06 00:27:51+00
12271	4417	1	uncommon	\N	2026-02-06 00:27:51+00	2026-02-06 00:27:51+00
12272	4417	3	uncommon	\N	2026-02-06 00:27:51+00	2026-02-06 00:27:51+00
12273	4417	28	uncommon	\N	2026-02-06 00:27:51+00	2026-02-06 00:27:51+00
12274	4417	4	uncommon	\N	2026-02-06 00:27:51+00	2026-02-06 00:27:51+00
12275	4418	2	uncommon	\N	2026-02-06 00:27:51+00	2026-02-06 00:27:51+00
12276	4418	1	uncommon	\N	2026-02-06 00:27:51+00	2026-02-06 00:27:51+00
12277	4418	3	uncommon	\N	2026-02-06 00:27:51+00	2026-02-06 00:27:51+00
12278	4418	28	uncommon	\N	2026-02-06 00:27:51+00	2026-02-06 00:27:51+00
12279	4418	4	uncommon	\N	2026-02-06 00:27:51+00	2026-02-06 00:27:51+00
12280	4419	27	uncommon	\N	2026-02-06 00:28:06+00	2026-02-06 00:28:06+00
12281	4419	25	uncommon	\N	2026-02-06 00:28:06+00	2026-02-06 00:28:06+00
12282	4419	2	uncommon	\N	2026-02-06 00:28:06+00	2026-02-06 00:28:06+00
12283	4419	3	uncommon	\N	2026-02-06 00:28:06+00	2026-02-06 00:28:06+00
12284	4419	4	uncommon	\N	2026-02-06 00:28:06+00	2026-02-06 00:28:06+00
12285	4420	27	uncommon	\N	2026-02-06 00:28:06+00	2026-02-06 00:28:06+00
12286	4420	25	uncommon	\N	2026-02-06 00:28:06+00	2026-02-06 00:28:06+00
12287	4420	2	uncommon	\N	2026-02-06 00:28:06+00	2026-02-06 00:28:06+00
12288	4420	3	uncommon	\N	2026-02-06 00:28:06+00	2026-02-06 00:28:06+00
12289	4420	4	uncommon	\N	2026-02-06 00:28:06+00	2026-02-06 00:28:06+00
12290	4421	27	uncommon	\N	2026-02-06 00:28:06+00	2026-02-06 00:28:06+00
12291	4421	25	uncommon	\N	2026-02-06 00:28:06+00	2026-02-06 00:28:06+00
12292	4421	2	uncommon	\N	2026-02-06 00:28:06+00	2026-02-06 00:28:06+00
12293	4421	3	uncommon	\N	2026-02-06 00:28:06+00	2026-02-06 00:28:06+00
12294	4421	4	uncommon	\N	2026-02-06 00:28:06+00	2026-02-06 00:28:06+00
12295	4422	27	uncommon	\N	2026-02-06 00:28:06+00	2026-02-06 00:28:06+00
12296	4422	25	uncommon	\N	2026-02-06 00:28:06+00	2026-02-06 00:28:06+00
12297	4422	2	uncommon	\N	2026-02-06 00:28:06+00	2026-02-06 00:28:06+00
12298	4422	1	uncommon	\N	2026-02-06 00:28:06+00	2026-02-06 00:28:06+00
12299	4422	3	uncommon	\N	2026-02-06 00:28:06+00	2026-02-06 00:28:06+00
12300	4422	4	uncommon	\N	2026-02-06 00:28:06+00	2026-02-06 00:28:06+00
12301	4423	27	uncommon	\N	2026-02-06 00:28:06+00	2026-02-06 00:28:06+00
12302	4423	25	uncommon	\N	2026-02-06 00:28:06+00	2026-02-06 00:28:06+00
12303	4423	2	uncommon	\N	2026-02-06 00:28:06+00	2026-02-06 00:28:06+00
12304	4423	1	uncommon	\N	2026-02-06 00:28:06+00	2026-02-06 00:28:06+00
12305	4423	3	uncommon	\N	2026-02-06 00:28:06+00	2026-02-06 00:28:06+00
12306	4423	4	uncommon	\N	2026-02-06 00:28:06+00	2026-02-06 00:28:06+00
12307	4424	27	uncommon	\N	2026-02-06 00:28:06+00	2026-02-06 00:28:06+00
12308	4424	25	uncommon	\N	2026-02-06 00:28:06+00	2026-02-06 00:28:06+00
12309	4424	2	uncommon	\N	2026-02-06 00:28:06+00	2026-02-06 00:28:06+00
12310	4424	1	uncommon	\N	2026-02-06 00:28:06+00	2026-02-06 00:28:06+00
12311	4424	3	uncommon	\N	2026-02-06 00:28:06+00	2026-02-06 00:28:06+00
12312	4424	4	uncommon	\N	2026-02-06 00:28:06+00	2026-02-06 00:28:06+00
12361	4435	2	uncommon	\N	2026-02-06 00:31:07+00	2026-02-06 00:31:07+00
12362	4435	3	uncommon	\N	2026-02-06 00:31:07+00	2026-02-06 00:31:07+00
12363	4435	4	uncommon	\N	2026-02-06 00:31:07+00	2026-02-06 00:31:07+00
12364	4436	2	uncommon	\N	2026-02-06 00:31:07+00	2026-02-06 00:31:07+00
12365	4436	3	uncommon	\N	2026-02-06 00:31:07+00	2026-02-06 00:31:07+00
12366	4436	4	uncommon	\N	2026-02-06 00:31:07+00	2026-02-06 00:31:07+00
12367	4437	2	uncommon	\N	2026-02-06 00:31:07+00	2026-02-06 00:31:07+00
12368	4437	3	uncommon	\N	2026-02-06 00:31:07+00	2026-02-06 00:31:07+00
12369	4437	4	uncommon	\N	2026-02-06 00:31:07+00	2026-02-06 00:31:07+00
12370	4438	2	uncommon	\N	2026-02-06 00:31:07+00	2026-02-06 00:31:07+00
12371	4438	1	uncommon	\N	2026-02-06 00:31:07+00	2026-02-06 00:31:07+00
12372	4438	3	uncommon	\N	2026-02-06 00:31:07+00	2026-02-06 00:31:07+00
12373	4438	4	uncommon	\N	2026-02-06 00:31:07+00	2026-02-06 00:31:07+00
12374	4439	2	uncommon	\N	2026-02-06 00:31:07+00	2026-02-06 00:31:07+00
12375	4439	1	uncommon	\N	2026-02-06 00:31:07+00	2026-02-06 00:31:07+00
12376	4439	3	uncommon	\N	2026-02-06 00:31:07+00	2026-02-06 00:31:07+00
12377	4439	4	uncommon	\N	2026-02-06 00:31:07+00	2026-02-06 00:31:07+00
12378	4440	2	uncommon	\N	2026-02-06 00:31:07+00	2026-02-06 00:31:07+00
12379	4440	1	uncommon	\N	2026-02-06 00:31:07+00	2026-02-06 00:31:07+00
12380	4440	3	uncommon	\N	2026-02-06 00:31:07+00	2026-02-06 00:31:07+00
12381	4440	4	uncommon	\N	2026-02-06 00:31:07+00	2026-02-06 00:31:07+00
12445	4458	2	uncommon	\N	2026-02-06 00:32:45+00	2026-02-06 00:32:45+00
12446	4458	1	uncommon	\N	2026-02-06 00:32:45+00	2026-02-06 00:32:45+00
12447	4458	3	uncommon	\N	2026-02-06 00:32:45+00	2026-02-06 00:32:45+00
12448	4458	28	uncommon	\N	2026-02-06 00:32:45+00	2026-02-06 00:32:45+00
12449	4459	2	uncommon	\N	2026-02-06 00:32:45+00	2026-02-06 00:32:45+00
12450	4459	1	uncommon	\N	2026-02-06 00:32:45+00	2026-02-06 00:32:45+00
12451	4459	3	uncommon	\N	2026-02-06 00:32:45+00	2026-02-06 00:32:45+00
12452	4459	28	uncommon	\N	2026-02-06 00:32:45+00	2026-02-06 00:32:45+00
12453	4460	2	uncommon	\N	2026-02-06 00:32:45+00	2026-02-06 00:32:45+00
12454	4460	1	uncommon	\N	2026-02-06 00:32:45+00	2026-02-06 00:32:45+00
12455	4460	3	uncommon	\N	2026-02-06 00:32:45+00	2026-02-06 00:32:45+00
12456	4460	28	uncommon	\N	2026-02-06 00:32:45+00	2026-02-06 00:32:45+00
12457	4461	2	uncommon	\N	2026-02-06 00:32:45+00	2026-02-06 00:32:45+00
12458	4461	3	uncommon	\N	2026-02-06 00:32:45+00	2026-02-06 00:32:45+00
12459	4461	28	uncommon	\N	2026-02-06 00:32:45+00	2026-02-06 00:32:45+00
12460	4462	2	uncommon	\N	2026-02-06 00:32:45+00	2026-02-06 00:32:45+00
12461	4462	3	uncommon	\N	2026-02-06 00:32:45+00	2026-02-06 00:32:45+00
12462	4462	28	uncommon	\N	2026-02-06 00:32:45+00	2026-02-06 00:32:45+00
12463	4463	2	uncommon	\N	2026-02-06 00:32:45+00	2026-02-06 00:32:45+00
12464	4463	3	uncommon	\N	2026-02-06 00:32:45+00	2026-02-06 00:32:45+00
12465	4463	28	uncommon	\N	2026-02-06 00:32:45+00	2026-02-06 00:32:45+00
12466	4464	2	uncommon	\N	2026-02-06 00:32:45+00	2026-02-06 00:32:45+00
12467	4464	3	uncommon	\N	2026-02-06 00:32:45+00	2026-02-06 00:32:45+00
12468	4464	28	uncommon	\N	2026-02-06 00:32:45+00	2026-02-06 00:32:45+00
12469	4465	27	uncommon	\N	2026-02-06 00:32:45+00	2026-02-06 00:32:45+00
12470	4466	27	uncommon	\N	2026-02-06 00:32:45+00	2026-02-06 00:32:45+00
12471	4467	27	uncommon	\N	2026-02-06 00:32:45+00	2026-02-06 00:32:45+00
12472	4468	27	uncommon	\N	2026-02-06 00:32:45+00	2026-02-06 00:32:45+00
12473	4469	2	uncommon	\N	2026-02-06 00:33:00+00	2026-02-06 00:33:00+00
12474	4469	1	uncommon	\N	2026-02-06 00:33:00+00	2026-02-06 00:33:00+00
12475	4469	3	uncommon	\N	2026-02-06 00:33:00+00	2026-02-06 00:33:00+00
12476	4469	4	uncommon	\N	2026-02-06 00:33:00+00	2026-02-06 00:33:00+00
12477	4470	2	uncommon	\N	2026-02-06 00:33:00+00	2026-02-06 00:33:00+00
12478	4470	1	uncommon	\N	2026-02-06 00:33:00+00	2026-02-06 00:33:00+00
12479	4470	3	uncommon	\N	2026-02-06 00:33:00+00	2026-02-06 00:33:00+00
12480	4470	4	uncommon	\N	2026-02-06 00:33:00+00	2026-02-06 00:33:00+00
12481	4471	2	uncommon	\N	2026-02-06 00:33:00+00	2026-02-06 00:33:00+00
12482	4471	1	uncommon	\N	2026-02-06 00:33:00+00	2026-02-06 00:33:00+00
12483	4471	3	uncommon	\N	2026-02-06 00:33:00+00	2026-02-06 00:33:00+00
12484	4471	4	uncommon	\N	2026-02-06 00:33:00+00	2026-02-06 00:33:00+00
12485	4472	27	uncommon	\N	2026-02-06 00:33:00+00	2026-02-06 00:33:00+00
12486	4472	44	uncommon	\N	2026-02-06 00:33:00+00	2026-02-06 00:33:00+00
12487	4472	2	uncommon	\N	2026-02-06 00:33:00+00	2026-02-06 00:33:00+00
12488	4472	3	uncommon	\N	2026-02-06 00:33:00+00	2026-02-06 00:33:00+00
12489	4472	4	uncommon	\N	2026-02-06 00:33:00+00	2026-02-06 00:33:00+00
12490	4473	27	uncommon	\N	2026-02-06 00:33:00+00	2026-02-06 00:33:00+00
12491	4473	44	uncommon	\N	2026-02-06 00:33:00+00	2026-02-06 00:33:00+00
12492	4473	2	uncommon	\N	2026-02-06 00:33:00+00	2026-02-06 00:33:00+00
12493	4473	3	uncommon	\N	2026-02-06 00:33:00+00	2026-02-06 00:33:00+00
12494	4473	4	uncommon	\N	2026-02-06 00:33:00+00	2026-02-06 00:33:00+00
12495	4474	27	uncommon	\N	2026-02-06 00:33:00+00	2026-02-06 00:33:00+00
12496	4474	44	uncommon	\N	2026-02-06 00:33:00+00	2026-02-06 00:33:00+00
12497	4474	2	uncommon	\N	2026-02-06 00:33:00+00	2026-02-06 00:33:00+00
12498	4474	3	uncommon	\N	2026-02-06 00:33:00+00	2026-02-06 00:33:00+00
12499	4474	4	uncommon	\N	2026-02-06 00:33:00+00	2026-02-06 00:33:00+00
12500	4475	31	uncommon	\N	2026-02-06 00:33:16+00	2026-02-06 00:33:16+00
12501	4475	1	uncommon	\N	2026-02-06 00:33:16+00	2026-02-06 00:33:16+00
12502	4475	28	uncommon	\N	2026-02-06 00:33:16+00	2026-02-06 00:33:16+00
12503	4475	4	uncommon	\N	2026-02-06 00:33:16+00	2026-02-06 00:33:16+00
12504	4476	31	uncommon	\N	2026-02-06 00:33:16+00	2026-02-06 00:33:16+00
12505	4476	1	uncommon	\N	2026-02-06 00:33:16+00	2026-02-06 00:33:16+00
12506	4476	28	uncommon	\N	2026-02-06 00:33:16+00	2026-02-06 00:33:16+00
12507	4476	4	uncommon	\N	2026-02-06 00:33:16+00	2026-02-06 00:33:16+00
12508	4477	31	uncommon	\N	2026-02-06 00:33:16+00	2026-02-06 00:33:16+00
12509	4477	1	uncommon	\N	2026-02-06 00:33:16+00	2026-02-06 00:33:16+00
12510	4477	28	uncommon	\N	2026-02-06 00:33:16+00	2026-02-06 00:33:16+00
12511	4477	4	uncommon	\N	2026-02-06 00:33:16+00	2026-02-06 00:33:16+00
12512	4478	31	uncommon	\N	2026-02-06 00:33:16+00	2026-02-06 00:33:16+00
12513	4478	1	uncommon	\N	2026-02-06 00:33:16+00	2026-02-06 00:33:16+00
12514	4478	28	uncommon	\N	2026-02-06 00:33:16+00	2026-02-06 00:33:16+00
12515	4478	4	uncommon	\N	2026-02-06 00:33:16+00	2026-02-06 00:33:16+00
12516	4479	14	uncommon	\N	2026-02-06 00:33:33+00	2026-02-06 00:33:33+00
12517	4479	1	uncommon	\N	2026-02-06 00:33:33+00	2026-02-06 00:33:33+00
12518	4479	4	uncommon	\N	2026-02-06 00:33:33+00	2026-02-06 00:33:33+00
12519	4480	14	uncommon	\N	2026-02-06 00:33:33+00	2026-02-06 00:33:33+00
12520	4480	1	uncommon	\N	2026-02-06 00:33:33+00	2026-02-06 00:33:33+00
12521	4480	4	uncommon	\N	2026-02-06 00:33:33+00	2026-02-06 00:33:33+00
12522	4481	14	uncommon	\N	2026-02-06 00:33:33+00	2026-02-06 00:33:33+00
12523	4481	1	uncommon	\N	2026-02-06 00:33:33+00	2026-02-06 00:33:33+00
12524	4481	4	uncommon	\N	2026-02-06 00:33:33+00	2026-02-06 00:33:33+00
12525	4482	14	uncommon	\N	2026-02-06 00:33:33+00	2026-02-06 00:33:33+00
12526	4482	1	uncommon	\N	2026-02-06 00:33:33+00	2026-02-06 00:33:33+00
12527	4482	4	uncommon	\N	2026-02-06 00:33:33+00	2026-02-06 00:33:33+00
12627	4511	23	uncommon	\N	2026-02-06 00:36:47+00	2026-02-06 00:36:47+00
12628	4511	27	uncommon	\N	2026-02-06 00:36:47+00	2026-02-06 00:36:47+00
12629	4511	32	uncommon	\N	2026-02-06 00:36:47+00	2026-02-06 00:36:47+00
12630	4511	2	uncommon	\N	2026-02-06 00:36:47+00	2026-02-06 00:36:47+00
12631	4511	14	uncommon	\N	2026-02-06 00:36:47+00	2026-02-06 00:36:47+00
12632	4511	1	uncommon	\N	2026-02-06 00:36:47+00	2026-02-06 00:36:47+00
12633	4512	23	uncommon	\N	2026-02-06 00:36:47+00	2026-02-06 00:36:47+00
12634	4512	27	uncommon	\N	2026-02-06 00:36:47+00	2026-02-06 00:36:47+00
12635	4512	32	uncommon	\N	2026-02-06 00:36:47+00	2026-02-06 00:36:47+00
12636	4512	2	uncommon	\N	2026-02-06 00:36:47+00	2026-02-06 00:36:47+00
12637	4512	14	uncommon	\N	2026-02-06 00:36:47+00	2026-02-06 00:36:47+00
12638	4512	1	uncommon	\N	2026-02-06 00:36:47+00	2026-02-06 00:36:47+00
12639	4513	23	uncommon	\N	2026-02-06 00:36:47+00	2026-02-06 00:36:47+00
12640	4513	27	uncommon	\N	2026-02-06 00:36:47+00	2026-02-06 00:36:47+00
12641	4513	32	uncommon	\N	2026-02-06 00:36:47+00	2026-02-06 00:36:47+00
12642	4513	2	uncommon	\N	2026-02-06 00:36:47+00	2026-02-06 00:36:47+00
12643	4513	14	uncommon	\N	2026-02-06 00:36:47+00	2026-02-06 00:36:47+00
12644	4513	1	uncommon	\N	2026-02-06 00:36:47+00	2026-02-06 00:36:47+00
12645	4514	23	uncommon	\N	2026-02-06 00:36:47+00	2026-02-06 00:36:47+00
12646	4514	27	uncommon	\N	2026-02-06 00:36:47+00	2026-02-06 00:36:47+00
12647	4514	32	uncommon	\N	2026-02-06 00:36:47+00	2026-02-06 00:36:47+00
12648	4514	2	uncommon	\N	2026-02-06 00:36:47+00	2026-02-06 00:36:47+00
12649	4514	14	uncommon	\N	2026-02-06 00:36:47+00	2026-02-06 00:36:47+00
12650	4514	1	uncommon	\N	2026-02-06 00:36:47+00	2026-02-06 00:36:47+00
12703	4530	32	uncommon	\N	2026-02-06 00:39:43+00	2026-02-06 00:39:43+00
12704	4530	2	uncommon	\N	2026-02-06 00:39:43+00	2026-02-06 00:39:43+00
12705	4530	1	uncommon	\N	2026-02-06 00:39:43+00	2026-02-06 00:39:43+00
12706	4530	3	uncommon	\N	2026-02-06 00:39:43+00	2026-02-06 00:39:43+00
12707	4530	4	uncommon	\N	2026-02-06 00:39:43+00	2026-02-06 00:39:43+00
12708	4531	32	uncommon	\N	2026-02-06 00:39:43+00	2026-02-06 00:39:43+00
12709	4531	2	uncommon	\N	2026-02-06 00:39:43+00	2026-02-06 00:39:43+00
12710	4531	1	uncommon	\N	2026-02-06 00:39:43+00	2026-02-06 00:39:43+00
12711	4531	3	uncommon	\N	2026-02-06 00:39:43+00	2026-02-06 00:39:43+00
12712	4531	4	uncommon	\N	2026-02-06 00:39:43+00	2026-02-06 00:39:43+00
12713	4532	32	uncommon	\N	2026-02-06 00:39:43+00	2026-02-06 00:39:43+00
12714	4532	2	uncommon	\N	2026-02-06 00:39:43+00	2026-02-06 00:39:43+00
12715	4532	1	uncommon	\N	2026-02-06 00:39:43+00	2026-02-06 00:39:43+00
12716	4532	3	uncommon	\N	2026-02-06 00:39:43+00	2026-02-06 00:39:43+00
12717	4532	4	uncommon	\N	2026-02-06 00:39:43+00	2026-02-06 00:39:43+00
12772	4551	18	uncommon	\N	2026-02-06 00:40:51+00	2026-02-06 00:40:51+00
12773	4551	27	uncommon	\N	2026-02-06 00:40:51+00	2026-02-06 00:40:51+00
12774	4551	3	uncommon	\N	2026-02-06 00:40:51+00	2026-02-06 00:40:51+00
12775	4551	16	uncommon	\N	2026-02-06 00:40:51+00	2026-02-06 00:40:51+00
12776	4552	18	uncommon	\N	2026-02-06 00:40:51+00	2026-02-06 00:40:51+00
12777	4552	27	uncommon	\N	2026-02-06 00:40:51+00	2026-02-06 00:40:51+00
12778	4552	3	uncommon	\N	2026-02-06 00:40:51+00	2026-02-06 00:40:51+00
12779	4552	16	uncommon	\N	2026-02-06 00:40:51+00	2026-02-06 00:40:51+00
12780	4553	18	uncommon	\N	2026-02-06 00:40:51+00	2026-02-06 00:40:51+00
12781	4553	27	uncommon	\N	2026-02-06 00:40:51+00	2026-02-06 00:40:51+00
12782	4553	3	uncommon	\N	2026-02-06 00:40:51+00	2026-02-06 00:40:51+00
12783	4553	16	uncommon	\N	2026-02-06 00:40:51+00	2026-02-06 00:40:51+00
12784	4554	18	uncommon	\N	2026-02-06 00:40:51+00	2026-02-06 00:40:51+00
12785	4554	27	uncommon	\N	2026-02-06 00:40:51+00	2026-02-06 00:40:51+00
12786	4554	3	uncommon	\N	2026-02-06 00:40:51+00	2026-02-06 00:40:51+00
12787	4554	16	uncommon	\N	2026-02-06 00:40:51+00	2026-02-06 00:40:51+00
12788	4555	18	uncommon	\N	2026-02-06 00:40:51+00	2026-02-06 00:40:51+00
12789	4555	27	uncommon	\N	2026-02-06 00:40:51+00	2026-02-06 00:40:51+00
12790	4555	1	uncommon	\N	2026-02-06 00:40:51+00	2026-02-06 00:40:51+00
12791	4555	3	uncommon	\N	2026-02-06 00:40:51+00	2026-02-06 00:40:51+00
12792	4555	16	uncommon	\N	2026-02-06 00:40:51+00	2026-02-06 00:40:51+00
12793	4556	18	uncommon	\N	2026-02-06 00:40:51+00	2026-02-06 00:40:51+00
12794	4556	27	uncommon	\N	2026-02-06 00:40:51+00	2026-02-06 00:40:51+00
12795	4556	1	uncommon	\N	2026-02-06 00:40:51+00	2026-02-06 00:40:51+00
12796	4556	3	uncommon	\N	2026-02-06 00:40:51+00	2026-02-06 00:40:51+00
12797	4556	16	uncommon	\N	2026-02-06 00:40:51+00	2026-02-06 00:40:51+00
12798	4557	18	uncommon	\N	2026-02-06 00:40:51+00	2026-02-06 00:40:51+00
12799	4557	27	uncommon	\N	2026-02-06 00:40:51+00	2026-02-06 00:40:51+00
12800	4557	1	uncommon	\N	2026-02-06 00:40:51+00	2026-02-06 00:40:51+00
12801	4557	3	uncommon	\N	2026-02-06 00:40:51+00	2026-02-06 00:40:51+00
12802	4557	16	uncommon	\N	2026-02-06 00:40:51+00	2026-02-06 00:40:51+00
12803	4558	18	uncommon	\N	2026-02-06 00:40:51+00	2026-02-06 00:40:51+00
12804	4558	27	uncommon	\N	2026-02-06 00:40:51+00	2026-02-06 00:40:51+00
12805	4558	1	uncommon	\N	2026-02-06 00:40:51+00	2026-02-06 00:40:51+00
12806	4558	3	uncommon	\N	2026-02-06 00:40:51+00	2026-02-06 00:40:51+00
12807	4558	16	uncommon	\N	2026-02-06 00:40:51+00	2026-02-06 00:40:51+00
12808	4559	15	uncommon	\N	2026-02-06 00:41:06+00	2026-02-06 00:41:06+00
12809	4559	14	uncommon	\N	2026-02-06 00:41:06+00	2026-02-06 00:41:06+00
12810	4559	1	uncommon	\N	2026-02-06 00:41:06+00	2026-02-06 00:41:06+00
12811	4559	4	uncommon	\N	2026-02-06 00:41:06+00	2026-02-06 00:41:06+00
12812	4560	15	uncommon	\N	2026-02-06 00:41:06+00	2026-02-06 00:41:06+00
12813	4560	14	uncommon	\N	2026-02-06 00:41:06+00	2026-02-06 00:41:06+00
12814	4560	1	uncommon	\N	2026-02-06 00:41:06+00	2026-02-06 00:41:06+00
12815	4560	4	uncommon	\N	2026-02-06 00:41:06+00	2026-02-06 00:41:06+00
12816	4561	15	uncommon	\N	2026-02-06 00:41:06+00	2026-02-06 00:41:06+00
12817	4561	14	uncommon	\N	2026-02-06 00:41:06+00	2026-02-06 00:41:06+00
12818	4561	1	uncommon	\N	2026-02-06 00:41:06+00	2026-02-06 00:41:06+00
12819	4561	4	uncommon	\N	2026-02-06 00:41:06+00	2026-02-06 00:41:06+00
12820	4562	15	uncommon	\N	2026-02-06 00:41:06+00	2026-02-06 00:41:06+00
12821	4562	14	uncommon	\N	2026-02-06 00:41:06+00	2026-02-06 00:41:06+00
12822	4562	1	uncommon	\N	2026-02-06 00:41:06+00	2026-02-06 00:41:06+00
12823	4562	4	uncommon	\N	2026-02-06 00:41:06+00	2026-02-06 00:41:06+00
12824	4563	27	uncommon	\N	2026-02-06 00:41:06+00	2026-02-06 00:41:06+00
12825	4564	27	uncommon	\N	2026-02-06 00:41:06+00	2026-02-06 00:41:06+00
12826	4565	27	uncommon	\N	2026-02-06 00:41:06+00	2026-02-06 00:41:06+00
12827	4566	20	uncommon	\N	2026-02-06 00:41:34+00	2026-02-06 00:41:34+00
12828	4566	25	uncommon	\N	2026-02-06 00:41:34+00	2026-02-06 00:41:34+00
12829	4566	2	uncommon	\N	2026-02-06 00:41:34+00	2026-02-06 00:41:34+00
12830	4566	1	uncommon	\N	2026-02-06 00:41:34+00	2026-02-06 00:41:34+00
12831	4566	3	uncommon	\N	2026-02-06 00:41:34+00	2026-02-06 00:41:34+00
12832	4566	4	uncommon	\N	2026-02-06 00:41:34+00	2026-02-06 00:41:34+00
12833	4567	20	uncommon	\N	2026-02-06 00:41:34+00	2026-02-06 00:41:34+00
12834	4567	25	uncommon	\N	2026-02-06 00:41:34+00	2026-02-06 00:41:34+00
12835	4567	2	uncommon	\N	2026-02-06 00:41:34+00	2026-02-06 00:41:34+00
12836	4567	1	uncommon	\N	2026-02-06 00:41:34+00	2026-02-06 00:41:34+00
12837	4567	3	uncommon	\N	2026-02-06 00:41:34+00	2026-02-06 00:41:34+00
12838	4567	4	uncommon	\N	2026-02-06 00:41:34+00	2026-02-06 00:41:34+00
12839	4568	20	uncommon	\N	2026-02-06 00:41:34+00	2026-02-06 00:41:34+00
12840	4568	25	uncommon	\N	2026-02-06 00:41:34+00	2026-02-06 00:41:34+00
12841	4568	2	uncommon	\N	2026-02-06 00:41:34+00	2026-02-06 00:41:34+00
12842	4568	1	uncommon	\N	2026-02-06 00:41:34+00	2026-02-06 00:41:34+00
12843	4568	3	uncommon	\N	2026-02-06 00:41:34+00	2026-02-06 00:41:34+00
12844	4568	4	uncommon	\N	2026-02-06 00:41:34+00	2026-02-06 00:41:34+00
12914	4581	29	uncommon	\N	2026-02-06 00:44:05+00	2026-02-06 00:44:05+00
12915	4581	22	uncommon	\N	2026-02-06 00:44:05+00	2026-02-06 00:44:05+00
12916	4581	3	uncommon	\N	2026-02-06 00:44:05+00	2026-02-06 00:44:05+00
12917	4582	29	uncommon	\N	2026-02-06 00:44:05+00	2026-02-06 00:44:05+00
12918	4582	22	uncommon	\N	2026-02-06 00:44:05+00	2026-02-06 00:44:05+00
12919	4582	3	uncommon	\N	2026-02-06 00:44:05+00	2026-02-06 00:44:05+00
12920	4584	29	uncommon	\N	2026-02-06 00:44:05+00	2026-02-06 00:44:05+00
12921	4584	22	uncommon	\N	2026-02-06 00:44:05+00	2026-02-06 00:44:05+00
12922	4584	3	uncommon	\N	2026-02-06 00:44:05+00	2026-02-06 00:44:05+00
12970	4597	2	uncommon	\N	2026-02-06 00:46:11+00	2026-02-06 00:46:11+00
12971	4597	14	uncommon	\N	2026-02-06 00:46:11+00	2026-02-06 00:46:11+00
12972	4597	1	uncommon	\N	2026-02-06 00:46:11+00	2026-02-06 00:46:11+00
12973	4597	3	uncommon	\N	2026-02-06 00:46:11+00	2026-02-06 00:46:11+00
12974	4597	4	uncommon	\N	2026-02-06 00:46:11+00	2026-02-06 00:46:11+00
12975	4598	2	uncommon	\N	2026-02-06 00:46:11+00	2026-02-06 00:46:11+00
12976	4598	14	uncommon	\N	2026-02-06 00:46:11+00	2026-02-06 00:46:11+00
12977	4598	1	uncommon	\N	2026-02-06 00:46:11+00	2026-02-06 00:46:11+00
12978	4598	3	uncommon	\N	2026-02-06 00:46:11+00	2026-02-06 00:46:11+00
12979	4598	4	uncommon	\N	2026-02-06 00:46:11+00	2026-02-06 00:46:11+00
12980	4599	2	uncommon	\N	2026-02-06 00:46:11+00	2026-02-06 00:46:11+00
12981	4599	14	uncommon	\N	2026-02-06 00:46:11+00	2026-02-06 00:46:11+00
12982	4599	1	uncommon	\N	2026-02-06 00:46:11+00	2026-02-06 00:46:11+00
12983	4599	3	uncommon	\N	2026-02-06 00:46:11+00	2026-02-06 00:46:11+00
12984	4599	4	uncommon	\N	2026-02-06 00:46:11+00	2026-02-06 00:46:11+00
12985	4600	2	uncommon	\N	2026-02-06 00:46:11+00	2026-02-06 00:46:11+00
12986	4600	14	uncommon	\N	2026-02-06 00:46:11+00	2026-02-06 00:46:11+00
12987	4600	1	uncommon	\N	2026-02-06 00:46:11+00	2026-02-06 00:46:11+00
12988	4600	3	uncommon	\N	2026-02-06 00:46:11+00	2026-02-06 00:46:11+00
12989	4600	4	uncommon	\N	2026-02-06 00:46:11+00	2026-02-06 00:46:11+00
12990	4601	2	uncommon	\N	2026-02-06 00:46:11+00	2026-02-06 00:46:11+00
12991	4601	14	uncommon	\N	2026-02-06 00:46:11+00	2026-02-06 00:46:11+00
12992	4601	1	uncommon	\N	2026-02-06 00:46:11+00	2026-02-06 00:46:11+00
12993	4601	3	uncommon	\N	2026-02-06 00:46:11+00	2026-02-06 00:46:11+00
12994	4601	4	uncommon	\N	2026-02-06 00:46:11+00	2026-02-06 00:46:11+00
12995	4602	2	uncommon	\N	2026-02-06 00:46:11+00	2026-02-06 00:46:11+00
12996	4602	14	uncommon	\N	2026-02-06 00:46:11+00	2026-02-06 00:46:11+00
12997	4602	3	uncommon	\N	2026-02-06 00:46:11+00	2026-02-06 00:46:11+00
12998	4602	4	uncommon	\N	2026-02-06 00:46:11+00	2026-02-06 00:46:11+00
12999	4603	2	uncommon	\N	2026-02-06 00:46:11+00	2026-02-06 00:46:11+00
13000	4603	14	uncommon	\N	2026-02-06 00:46:11+00	2026-02-06 00:46:11+00
13001	4603	3	uncommon	\N	2026-02-06 00:46:11+00	2026-02-06 00:46:11+00
13002	4603	4	uncommon	\N	2026-02-06 00:46:11+00	2026-02-06 00:46:11+00
13003	4604	2	uncommon	\N	2026-02-06 00:46:11+00	2026-02-06 00:46:11+00
13004	4604	14	uncommon	\N	2026-02-06 00:46:11+00	2026-02-06 00:46:11+00
13005	4604	3	uncommon	\N	2026-02-06 00:46:11+00	2026-02-06 00:46:11+00
13006	4604	4	uncommon	\N	2026-02-06 00:46:11+00	2026-02-06 00:46:11+00
13007	4605	2	uncommon	\N	2026-02-06 00:46:11+00	2026-02-06 00:46:11+00
13008	4605	14	uncommon	\N	2026-02-06 00:46:11+00	2026-02-06 00:46:11+00
13009	4605	3	uncommon	\N	2026-02-06 00:46:11+00	2026-02-06 00:46:11+00
13010	4605	4	uncommon	\N	2026-02-06 00:46:11+00	2026-02-06 00:46:11+00
13011	4606	2	uncommon	\N	2026-02-06 00:46:11+00	2026-02-06 00:46:11+00
13012	4606	14	uncommon	\N	2026-02-06 00:46:11+00	2026-02-06 00:46:11+00
13013	4606	3	uncommon	\N	2026-02-06 00:46:11+00	2026-02-06 00:46:11+00
13014	4606	4	uncommon	\N	2026-02-06 00:46:11+00	2026-02-06 00:46:11+00
13048	4616	27	uncommon	\N	2026-02-06 00:47:06+00	2026-02-06 00:47:06+00
13049	4616	3	uncommon	\N	2026-02-06 00:47:06+00	2026-02-06 00:47:06+00
13050	4616	4	uncommon	\N	2026-02-06 00:47:06+00	2026-02-06 00:47:06+00
13051	4617	27	uncommon	\N	2026-02-06 00:47:06+00	2026-02-06 00:47:06+00
13052	4617	3	uncommon	\N	2026-02-06 00:47:06+00	2026-02-06 00:47:06+00
13053	4617	4	uncommon	\N	2026-02-06 00:47:06+00	2026-02-06 00:47:06+00
13054	4618	27	uncommon	\N	2026-02-06 00:47:06+00	2026-02-06 00:47:06+00
13055	4618	3	uncommon	\N	2026-02-06 00:47:06+00	2026-02-06 00:47:06+00
13056	4618	4	uncommon	\N	2026-02-06 00:47:06+00	2026-02-06 00:47:06+00
13084	4624	2	uncommon	\N	2026-02-06 01:03:18+00	2026-02-06 01:03:18+00
13085	4624	1	uncommon	\N	2026-02-06 01:03:18+00	2026-02-06 01:03:18+00
13086	4624	3	uncommon	\N	2026-02-06 01:03:18+00	2026-02-06 01:03:18+00
13087	4625	2	uncommon	\N	2026-02-06 01:03:18+00	2026-02-06 01:03:18+00
13088	4625	1	uncommon	\N	2026-02-06 01:03:18+00	2026-02-06 01:03:18+00
13089	4625	3	uncommon	\N	2026-02-06 01:03:18+00	2026-02-06 01:03:18+00
13090	4626	2	uncommon	\N	2026-02-06 01:03:18+00	2026-02-06 01:03:18+00
13091	4626	1	uncommon	\N	2026-02-06 01:03:18+00	2026-02-06 01:03:18+00
13092	4626	3	uncommon	\N	2026-02-06 01:03:18+00	2026-02-06 01:03:18+00
13093	4627	2	uncommon	\N	2026-02-06 01:03:18+00	2026-02-06 01:03:18+00
13094	4627	3	uncommon	\N	2026-02-06 01:03:18+00	2026-02-06 01:03:18+00
13095	4628	2	uncommon	\N	2026-02-06 01:03:18+00	2026-02-06 01:03:18+00
13096	4628	3	uncommon	\N	2026-02-06 01:03:18+00	2026-02-06 01:03:18+00
13097	4629	2	uncommon	\N	2026-02-06 01:03:18+00	2026-02-06 01:03:18+00
13098	4629	3	uncommon	\N	2026-02-06 01:03:18+00	2026-02-06 01:03:18+00
13099	4629	16	uncommon	\N	2026-02-06 01:03:18+00	2026-02-06 01:03:18+00
13100	4630	2	uncommon	\N	2026-02-06 01:03:18+00	2026-02-06 01:03:18+00
13101	4630	3	uncommon	\N	2026-02-06 01:03:18+00	2026-02-06 01:03:18+00
13102	4630	16	uncommon	\N	2026-02-06 01:03:18+00	2026-02-06 01:03:18+00
13103	4630	4	uncommon	\N	2026-02-06 01:03:18+00	2026-02-06 01:03:18+00
13104	4631	27	uncommon	\N	2026-02-06 01:03:35+00	2026-02-06 01:03:35+00
13105	4631	3	uncommon	\N	2026-02-06 01:03:35+00	2026-02-06 01:03:35+00
13106	4631	4	uncommon	\N	2026-02-06 01:03:35+00	2026-02-06 01:03:35+00
13107	4632	27	uncommon	\N	2026-02-06 01:03:35+00	2026-02-06 01:03:35+00
13108	4632	3	uncommon	\N	2026-02-06 01:03:35+00	2026-02-06 01:03:35+00
13109	4632	4	uncommon	\N	2026-02-06 01:03:35+00	2026-02-06 01:03:35+00
13110	4633	27	uncommon	\N	2026-02-06 01:03:35+00	2026-02-06 01:03:35+00
13111	4633	3	uncommon	\N	2026-02-06 01:03:35+00	2026-02-06 01:03:35+00
13112	4633	4	uncommon	\N	2026-02-06 01:03:35+00	2026-02-06 01:03:35+00
13113	4634	27	uncommon	\N	2026-02-06 01:03:35+00	2026-02-06 01:03:35+00
13114	4634	1	uncommon	\N	2026-02-06 01:03:35+00	2026-02-06 01:03:35+00
13115	4634	3	uncommon	\N	2026-02-06 01:03:35+00	2026-02-06 01:03:35+00
13116	4634	4	uncommon	\N	2026-02-06 01:03:35+00	2026-02-06 01:03:35+00
13117	4635	27	uncommon	\N	2026-02-06 01:03:35+00	2026-02-06 01:03:35+00
13118	4635	1	uncommon	\N	2026-02-06 01:03:35+00	2026-02-06 01:03:35+00
13119	4635	3	uncommon	\N	2026-02-06 01:03:35+00	2026-02-06 01:03:35+00
13120	4635	4	uncommon	\N	2026-02-06 01:03:35+00	2026-02-06 01:03:35+00
13121	4636	27	uncommon	\N	2026-02-06 01:03:35+00	2026-02-06 01:03:35+00
13122	4636	1	uncommon	\N	2026-02-06 01:03:35+00	2026-02-06 01:03:35+00
13123	4636	3	uncommon	\N	2026-02-06 01:03:35+00	2026-02-06 01:03:35+00
13124	4636	4	uncommon	\N	2026-02-06 01:03:35+00	2026-02-06 01:03:35+00
13125	4637	18	uncommon	\N	2026-02-06 01:03:49+00	2026-02-06 01:03:49+00
13126	4637	1	uncommon	\N	2026-02-06 01:03:49+00	2026-02-06 01:03:49+00
13127	4637	16	uncommon	\N	2026-02-06 01:03:49+00	2026-02-06 01:03:49+00
13128	4638	18	uncommon	\N	2026-02-06 01:03:49+00	2026-02-06 01:03:49+00
13129	4638	1	uncommon	\N	2026-02-06 01:03:49+00	2026-02-06 01:03:49+00
13130	4638	16	uncommon	\N	2026-02-06 01:03:49+00	2026-02-06 01:03:49+00
13131	4639	18	uncommon	\N	2026-02-06 01:03:49+00	2026-02-06 01:03:49+00
13132	4639	1	uncommon	\N	2026-02-06 01:03:49+00	2026-02-06 01:03:49+00
13133	4639	16	uncommon	\N	2026-02-06 01:03:49+00	2026-02-06 01:03:49+00
13134	4640	18	uncommon	\N	2026-02-06 01:03:49+00	2026-02-06 01:03:49+00
13135	4640	1	uncommon	\N	2026-02-06 01:03:49+00	2026-02-06 01:03:49+00
13136	4640	16	uncommon	\N	2026-02-06 01:03:49+00	2026-02-06 01:03:49+00
13137	4641	18	uncommon	\N	2026-02-06 01:03:49+00	2026-02-06 01:03:49+00
13138	4641	16	uncommon	\N	2026-02-06 01:03:49+00	2026-02-06 01:03:49+00
13139	4642	18	uncommon	\N	2026-02-06 01:03:49+00	2026-02-06 01:03:49+00
13140	4642	16	uncommon	\N	2026-02-06 01:03:49+00	2026-02-06 01:03:49+00
13141	4643	18	uncommon	\N	2026-02-06 01:03:49+00	2026-02-06 01:03:49+00
13142	4643	16	uncommon	\N	2026-02-06 01:03:49+00	2026-02-06 01:03:49+00
13149	4647	3	uncommon	\N	2026-02-06 01:04:29+00	2026-02-06 01:04:29+00
13150	4647	16	uncommon	\N	2026-02-06 01:04:29+00	2026-02-06 01:04:29+00
13151	4647	28	uncommon	\N	2026-02-06 01:04:29+00	2026-02-06 01:04:29+00
13152	4648	3	uncommon	\N	2026-02-06 01:04:29+00	2026-02-06 01:04:29+00
13153	4648	16	uncommon	\N	2026-02-06 01:04:29+00	2026-02-06 01:04:29+00
13154	4648	28	uncommon	\N	2026-02-06 01:04:29+00	2026-02-06 01:04:29+00
13155	4649	3	uncommon	\N	2026-02-06 01:04:29+00	2026-02-06 01:04:29+00
13156	4649	16	uncommon	\N	2026-02-06 01:04:29+00	2026-02-06 01:04:29+00
13157	4649	28	uncommon	\N	2026-02-06 01:04:29+00	2026-02-06 01:04:29+00
13158	4650	2	uncommon	\N	2026-02-06 01:04:58+00	2026-02-06 01:04:58+00
13159	4650	14	uncommon	\N	2026-02-06 01:04:58+00	2026-02-06 01:04:58+00
13160	4650	21	uncommon	\N	2026-02-06 01:04:58+00	2026-02-06 01:04:58+00
13161	4650	1	uncommon	\N	2026-02-06 01:04:58+00	2026-02-06 01:04:58+00
13162	4650	3	uncommon	\N	2026-02-06 01:04:58+00	2026-02-06 01:04:58+00
13163	4650	4	uncommon	\N	2026-02-06 01:04:58+00	2026-02-06 01:04:58+00
13164	4651	2	uncommon	\N	2026-02-06 01:04:58+00	2026-02-06 01:04:58+00
13165	4651	14	uncommon	\N	2026-02-06 01:04:58+00	2026-02-06 01:04:58+00
13166	4651	21	uncommon	\N	2026-02-06 01:04:58+00	2026-02-06 01:04:58+00
13167	4651	1	uncommon	\N	2026-02-06 01:04:58+00	2026-02-06 01:04:58+00
13168	4651	3	uncommon	\N	2026-02-06 01:04:58+00	2026-02-06 01:04:58+00
13169	4651	4	uncommon	\N	2026-02-06 01:04:58+00	2026-02-06 01:04:58+00
13170	4652	2	uncommon	\N	2026-02-06 01:04:58+00	2026-02-06 01:04:58+00
13171	4652	14	uncommon	\N	2026-02-06 01:04:58+00	2026-02-06 01:04:58+00
13172	4652	21	uncommon	\N	2026-02-06 01:04:58+00	2026-02-06 01:04:58+00
13173	4652	1	uncommon	\N	2026-02-06 01:04:58+00	2026-02-06 01:04:58+00
13174	4652	3	uncommon	\N	2026-02-06 01:04:58+00	2026-02-06 01:04:58+00
13175	4652	4	uncommon	\N	2026-02-06 01:04:58+00	2026-02-06 01:04:58+00
13176	4653	2	uncommon	\N	2026-02-06 01:04:58+00	2026-02-06 01:04:58+00
13177	4653	14	uncommon	\N	2026-02-06 01:04:58+00	2026-02-06 01:04:58+00
13178	4653	21	uncommon	\N	2026-02-06 01:04:58+00	2026-02-06 01:04:58+00
13179	4653	1	uncommon	\N	2026-02-06 01:04:58+00	2026-02-06 01:04:58+00
13180	4653	3	uncommon	\N	2026-02-06 01:04:58+00	2026-02-06 01:04:58+00
13181	4653	4	uncommon	\N	2026-02-06 01:04:58+00	2026-02-06 01:04:58+00
13182	4654	2	uncommon	\N	2026-02-06 01:04:58+00	2026-02-06 01:04:58+00
13183	4654	14	uncommon	\N	2026-02-06 01:04:58+00	2026-02-06 01:04:58+00
13184	4654	21	uncommon	\N	2026-02-06 01:04:58+00	2026-02-06 01:04:58+00
13185	4654	1	uncommon	\N	2026-02-06 01:04:58+00	2026-02-06 01:04:58+00
13186	4654	3	uncommon	\N	2026-02-06 01:04:58+00	2026-02-06 01:04:58+00
13187	4654	4	uncommon	\N	2026-02-06 01:04:58+00	2026-02-06 01:04:58+00
13238	4670	27	uncommon	\N	2026-02-06 01:06:32+00	2026-02-06 01:06:32+00
13239	4671	27	uncommon	\N	2026-02-06 01:06:32+00	2026-02-06 01:06:32+00
13240	4672	27	uncommon	\N	2026-02-06 01:06:32+00	2026-02-06 01:06:32+00
13241	4673	26	uncommon	\N	2026-02-06 01:06:45+00	2026-02-06 01:06:45+00
13242	4673	20	uncommon	\N	2026-02-06 01:06:45+00	2026-02-06 01:06:45+00
13243	4673	32	uncommon	\N	2026-02-06 01:06:45+00	2026-02-06 01:06:45+00
13244	4673	25	uncommon	\N	2026-02-06 01:06:45+00	2026-02-06 01:06:45+00
13245	4673	2	uncommon	\N	2026-02-06 01:06:45+00	2026-02-06 01:06:45+00
13246	4673	4	uncommon	\N	2026-02-06 01:06:45+00	2026-02-06 01:06:45+00
13247	4674	26	uncommon	\N	2026-02-06 01:06:45+00	2026-02-06 01:06:45+00
13248	4674	20	uncommon	\N	2026-02-06 01:06:45+00	2026-02-06 01:06:45+00
13249	4674	32	uncommon	\N	2026-02-06 01:06:45+00	2026-02-06 01:06:45+00
13250	4674	25	uncommon	\N	2026-02-06 01:06:45+00	2026-02-06 01:06:45+00
13251	4674	2	uncommon	\N	2026-02-06 01:06:45+00	2026-02-06 01:06:45+00
13252	4674	4	uncommon	\N	2026-02-06 01:06:45+00	2026-02-06 01:06:45+00
13253	4675	26	uncommon	\N	2026-02-06 01:06:45+00	2026-02-06 01:06:45+00
13254	4675	20	uncommon	\N	2026-02-06 01:06:45+00	2026-02-06 01:06:45+00
13255	4675	32	uncommon	\N	2026-02-06 01:06:45+00	2026-02-06 01:06:45+00
13256	4675	25	uncommon	\N	2026-02-06 01:06:45+00	2026-02-06 01:06:45+00
13257	4675	2	uncommon	\N	2026-02-06 01:06:45+00	2026-02-06 01:06:45+00
13258	4675	4	uncommon	\N	2026-02-06 01:06:45+00	2026-02-06 01:06:45+00
13259	4676	26	uncommon	\N	2026-02-06 01:06:45+00	2026-02-06 01:06:45+00
13260	4676	20	uncommon	\N	2026-02-06 01:06:45+00	2026-02-06 01:06:45+00
13261	4676	32	uncommon	\N	2026-02-06 01:06:45+00	2026-02-06 01:06:45+00
13262	4676	25	uncommon	\N	2026-02-06 01:06:45+00	2026-02-06 01:06:45+00
13263	4676	2	uncommon	\N	2026-02-06 01:06:45+00	2026-02-06 01:06:45+00
13264	4676	4	uncommon	\N	2026-02-06 01:06:45+00	2026-02-06 01:06:45+00
13303	4685	2	uncommon	\N	2026-02-06 01:07:35+00	2026-02-06 01:07:35+00
13304	4685	1	uncommon	\N	2026-02-06 01:07:35+00	2026-02-06 01:07:35+00
13305	4685	3	uncommon	\N	2026-02-06 01:07:35+00	2026-02-06 01:07:35+00
13306	4685	4	uncommon	\N	2026-02-06 01:07:35+00	2026-02-06 01:07:35+00
13307	4686	2	uncommon	\N	2026-02-06 01:07:35+00	2026-02-06 01:07:35+00
13308	4686	1	uncommon	\N	2026-02-06 01:07:35+00	2026-02-06 01:07:35+00
13309	4686	3	uncommon	\N	2026-02-06 01:07:35+00	2026-02-06 01:07:35+00
13310	4686	4	uncommon	\N	2026-02-06 01:07:35+00	2026-02-06 01:07:35+00
13311	4687	2	uncommon	\N	2026-02-06 01:07:35+00	2026-02-06 01:07:35+00
13312	4687	1	uncommon	\N	2026-02-06 01:07:35+00	2026-02-06 01:07:35+00
13313	4687	3	uncommon	\N	2026-02-06 01:07:35+00	2026-02-06 01:07:35+00
13314	4687	4	uncommon	\N	2026-02-06 01:07:35+00	2026-02-06 01:07:35+00
13315	4688	27	uncommon	\N	2026-02-06 01:07:58+00	2026-02-06 01:07:58+00
13316	4688	1	uncommon	\N	2026-02-06 01:07:58+00	2026-02-06 01:07:58+00
13317	4688	3	uncommon	\N	2026-02-06 01:07:58+00	2026-02-06 01:07:58+00
13318	4688	4	uncommon	\N	2026-02-06 01:07:58+00	2026-02-06 01:07:58+00
13319	4689	27	uncommon	\N	2026-02-06 01:07:58+00	2026-02-06 01:07:58+00
13320	4689	1	uncommon	\N	2026-02-06 01:07:58+00	2026-02-06 01:07:58+00
13321	4689	3	uncommon	\N	2026-02-06 01:07:58+00	2026-02-06 01:07:58+00
13322	4689	4	uncommon	\N	2026-02-06 01:07:58+00	2026-02-06 01:07:58+00
13323	4690	27	uncommon	\N	2026-02-06 01:07:58+00	2026-02-06 01:07:58+00
13324	4690	1	uncommon	\N	2026-02-06 01:07:58+00	2026-02-06 01:07:58+00
13325	4690	3	uncommon	\N	2026-02-06 01:07:58+00	2026-02-06 01:07:58+00
13326	4690	4	uncommon	\N	2026-02-06 01:07:58+00	2026-02-06 01:07:58+00
13327	4691	27	uncommon	\N	2026-02-06 01:07:58+00	2026-02-06 01:07:58+00
13328	4691	1	uncommon	\N	2026-02-06 01:07:58+00	2026-02-06 01:07:58+00
13329	4691	3	uncommon	\N	2026-02-06 01:07:58+00	2026-02-06 01:07:58+00
13330	4691	4	uncommon	\N	2026-02-06 01:07:58+00	2026-02-06 01:07:58+00
13331	4692	27	uncommon	\N	2026-02-06 01:07:58+00	2026-02-06 01:07:58+00
13332	4692	1	uncommon	\N	2026-02-06 01:07:58+00	2026-02-06 01:07:58+00
13333	4692	3	uncommon	\N	2026-02-06 01:07:58+00	2026-02-06 01:07:58+00
13334	4692	4	uncommon	\N	2026-02-06 01:07:58+00	2026-02-06 01:07:58+00
13335	4693	27	uncommon	\N	2026-02-06 01:07:58+00	2026-02-06 01:07:58+00
13336	4693	1	uncommon	\N	2026-02-06 01:07:58+00	2026-02-06 01:07:58+00
13337	4693	3	uncommon	\N	2026-02-06 01:07:58+00	2026-02-06 01:07:58+00
13338	4693	4	uncommon	\N	2026-02-06 01:07:58+00	2026-02-06 01:07:58+00
13339	4694	27	uncommon	\N	2026-02-06 01:08:11+00	2026-02-06 01:08:11+00
13340	4694	1	uncommon	\N	2026-02-06 01:08:11+00	2026-02-06 01:08:11+00
13341	4695	27	uncommon	\N	2026-02-06 01:08:11+00	2026-02-06 01:08:11+00
13342	4695	1	uncommon	\N	2026-02-06 01:08:11+00	2026-02-06 01:08:11+00
13343	4696	27	uncommon	\N	2026-02-06 01:08:11+00	2026-02-06 01:08:11+00
13344	4696	1	uncommon	\N	2026-02-06 01:08:11+00	2026-02-06 01:08:11+00
13345	4697	27	uncommon	\N	2026-02-06 01:08:11+00	2026-02-06 01:08:11+00
13346	4697	1	uncommon	\N	2026-02-06 01:08:11+00	2026-02-06 01:08:11+00
13347	4698	27	uncommon	\N	2026-02-06 01:08:11+00	2026-02-06 01:08:11+00
13348	4698	1	uncommon	\N	2026-02-06 01:08:11+00	2026-02-06 01:08:11+00
13349	4699	27	uncommon	\N	2026-02-06 01:08:11+00	2026-02-06 01:08:11+00
13350	4699	1	uncommon	\N	2026-02-06 01:08:11+00	2026-02-06 01:08:11+00
13351	4700	27	uncommon	\N	2026-02-06 01:08:11+00	2026-02-06 01:08:11+00
13352	4700	1	uncommon	\N	2026-02-06 01:08:11+00	2026-02-06 01:08:11+00
13353	4708	2	uncommon	\N	2026-02-06 01:08:35+00	2026-02-06 01:08:35+00
13354	4708	1	uncommon	\N	2026-02-06 01:08:35+00	2026-02-06 01:08:35+00
13355	4709	2	uncommon	\N	2026-02-06 01:08:35+00	2026-02-06 01:08:35+00
13356	4709	1	uncommon	\N	2026-02-06 01:08:35+00	2026-02-06 01:08:35+00
13357	4710	2	uncommon	\N	2026-02-06 01:08:35+00	2026-02-06 01:08:35+00
13358	4710	1	uncommon	\N	2026-02-06 01:08:35+00	2026-02-06 01:08:35+00
13359	4711	27	uncommon	\N	2026-02-06 01:08:45+00	2026-02-06 01:08:45+00
13360	4711	1	uncommon	\N	2026-02-06 01:08:45+00	2026-02-06 01:08:45+00
13361	4711	3	uncommon	\N	2026-02-06 01:08:45+00	2026-02-06 01:08:45+00
13362	4711	4	uncommon	\N	2026-02-06 01:08:45+00	2026-02-06 01:08:45+00
13363	4712	27	uncommon	\N	2026-02-06 01:08:45+00	2026-02-06 01:08:45+00
13364	4712	1	uncommon	\N	2026-02-06 01:08:45+00	2026-02-06 01:08:45+00
13365	4712	3	uncommon	\N	2026-02-06 01:08:45+00	2026-02-06 01:08:45+00
13366	4712	4	uncommon	\N	2026-02-06 01:08:45+00	2026-02-06 01:08:45+00
13367	4713	27	uncommon	\N	2026-02-06 01:08:45+00	2026-02-06 01:08:45+00
13368	4713	1	uncommon	\N	2026-02-06 01:08:45+00	2026-02-06 01:08:45+00
13369	4713	3	uncommon	\N	2026-02-06 01:08:45+00	2026-02-06 01:08:45+00
13370	4713	4	uncommon	\N	2026-02-06 01:08:45+00	2026-02-06 01:08:45+00
13371	4714	27	uncommon	\N	2026-02-06 01:08:45+00	2026-02-06 01:08:45+00
13372	4714	3	uncommon	\N	2026-02-06 01:08:45+00	2026-02-06 01:08:45+00
13373	4714	4	uncommon	\N	2026-02-06 01:08:45+00	2026-02-06 01:08:45+00
13374	4715	27	uncommon	\N	2026-02-06 01:08:45+00	2026-02-06 01:08:45+00
13375	4715	3	uncommon	\N	2026-02-06 01:08:45+00	2026-02-06 01:08:45+00
13376	4715	4	uncommon	\N	2026-02-06 01:08:45+00	2026-02-06 01:08:45+00
13377	4716	27	uncommon	\N	2026-02-06 01:08:45+00	2026-02-06 01:08:45+00
13378	4716	3	uncommon	\N	2026-02-06 01:08:45+00	2026-02-06 01:08:45+00
13379	4716	4	uncommon	\N	2026-02-06 01:08:45+00	2026-02-06 01:08:45+00
13380	4717	27	uncommon	\N	2026-02-06 01:08:45+00	2026-02-06 01:08:45+00
13381	4717	3	uncommon	\N	2026-02-06 01:08:45+00	2026-02-06 01:08:45+00
13382	4717	4	uncommon	\N	2026-02-06 01:08:45+00	2026-02-06 01:08:45+00
13476	4729	26	uncommon	\N	2026-02-18 22:17:33+00	2026-02-18 22:17:33+00
13477	4729	24	uncommon	\N	2026-02-18 22:17:33+00	2026-02-18 22:17:33+00
13478	4729	20	uncommon	\N	2026-02-18 22:17:33+00	2026-02-18 22:17:33+00
13479	4729	25	uncommon	\N	2026-02-18 22:17:33+00	2026-02-18 22:17:33+00
13480	4729	2	uncommon	\N	2026-02-18 22:17:33+00	2026-02-18 22:17:33+00
13481	4729	1	uncommon	\N	2026-02-18 22:17:33+00	2026-02-18 22:17:33+00
13482	4729	4	uncommon	\N	2026-02-18 22:17:33+00	2026-02-18 22:17:33+00
13483	4730	26	uncommon	\N	2026-02-18 22:17:33+00	2026-02-18 22:17:33+00
13484	4730	24	uncommon	\N	2026-02-18 22:17:33+00	2026-02-18 22:17:33+00
13485	4730	20	uncommon	\N	2026-02-18 22:17:33+00	2026-02-18 22:17:33+00
13486	4730	25	uncommon	\N	2026-02-18 22:17:33+00	2026-02-18 22:17:33+00
13487	4730	2	uncommon	\N	2026-02-18 22:17:33+00	2026-02-18 22:17:33+00
13488	4730	1	uncommon	\N	2026-02-18 22:17:33+00	2026-02-18 22:17:33+00
13489	4730	4	uncommon	\N	2026-02-18 22:17:33+00	2026-02-18 22:17:33+00
13490	4731	26	uncommon	\N	2026-02-18 22:17:33+00	2026-02-18 22:17:33+00
13491	4731	24	uncommon	\N	2026-02-18 22:17:33+00	2026-02-18 22:17:33+00
13492	4731	20	uncommon	\N	2026-02-18 22:17:33+00	2026-02-18 22:17:33+00
13493	4731	25	uncommon	\N	2026-02-18 22:17:33+00	2026-02-18 22:17:33+00
13494	4731	2	uncommon	\N	2026-02-18 22:17:33+00	2026-02-18 22:17:33+00
13495	4731	1	uncommon	\N	2026-02-18 22:17:33+00	2026-02-18 22:17:33+00
13496	4731	4	uncommon	\N	2026-02-18 22:17:33+00	2026-02-18 22:17:33+00
13497	4732	26	uncommon	\N	2026-02-18 22:17:33+00	2026-02-18 22:17:33+00
13498	4732	24	uncommon	\N	2026-02-18 22:17:33+00	2026-02-18 22:17:33+00
13499	4732	20	uncommon	\N	2026-02-18 22:17:33+00	2026-02-18 22:17:33+00
13500	4732	25	uncommon	\N	2026-02-18 22:17:33+00	2026-02-18 22:17:33+00
13501	4732	2	uncommon	\N	2026-02-18 22:17:33+00	2026-02-18 22:17:33+00
13502	4732	1	uncommon	\N	2026-02-18 22:17:33+00	2026-02-18 22:17:33+00
13503	4732	4	uncommon	\N	2026-02-18 22:17:33+00	2026-02-18 22:17:33+00
13504	4733	26	uncommon	\N	2026-02-18 22:17:33+00	2026-02-18 22:17:33+00
13505	4733	24	uncommon	\N	2026-02-18 22:17:33+00	2026-02-18 22:17:33+00
13506	4733	20	uncommon	\N	2026-02-18 22:17:33+00	2026-02-18 22:17:33+00
13507	4733	25	uncommon	\N	2026-02-18 22:17:33+00	2026-02-18 22:17:33+00
13508	4733	2	uncommon	\N	2026-02-18 22:17:33+00	2026-02-18 22:17:33+00
13509	4733	1	uncommon	\N	2026-02-18 22:17:33+00	2026-02-18 22:17:33+00
13510	4733	4	uncommon	\N	2026-02-18 22:17:33+00	2026-02-18 22:17:33+00
13511	4734	2	uncommon	\N	2026-02-18 22:18:28+00	2026-02-18 22:18:28+00
13512	4734	3	uncommon	\N	2026-02-18 22:18:28+00	2026-02-18 22:18:28+00
13513	4734	16	uncommon	\N	2026-02-18 22:18:28+00	2026-02-18 22:18:28+00
13514	4735	2	uncommon	\N	2026-02-18 22:18:28+00	2026-02-18 22:18:28+00
13515	4735	3	uncommon	\N	2026-02-18 22:18:28+00	2026-02-18 22:18:28+00
13516	4735	16	uncommon	\N	2026-02-18 22:18:28+00	2026-02-18 22:18:28+00
13517	4736	2	uncommon	\N	2026-02-18 22:18:28+00	2026-02-18 22:18:28+00
13518	4736	3	uncommon	\N	2026-02-18 22:18:28+00	2026-02-18 22:18:28+00
13519	4736	16	uncommon	\N	2026-02-18 22:18:28+00	2026-02-18 22:18:28+00
13520	4737	2	uncommon	\N	2026-02-18 22:18:28+00	2026-02-18 22:18:28+00
13521	4737	3	uncommon	\N	2026-02-18 22:18:28+00	2026-02-18 22:18:28+00
13522	4737	16	uncommon	\N	2026-02-18 22:18:28+00	2026-02-18 22:18:28+00
13523	4738	2	uncommon	\N	2026-02-18 22:18:28+00	2026-02-18 22:18:28+00
13524	4738	1	uncommon	\N	2026-02-18 22:18:28+00	2026-02-18 22:18:28+00
13525	4738	3	uncommon	\N	2026-02-18 22:18:28+00	2026-02-18 22:18:28+00
13526	4738	4	uncommon	\N	2026-02-18 22:18:28+00	2026-02-18 22:18:28+00
13527	4739	2	uncommon	\N	2026-02-18 22:18:28+00	2026-02-18 22:18:28+00
13528	4739	1	uncommon	\N	2026-02-18 22:18:28+00	2026-02-18 22:18:28+00
13529	4739	3	uncommon	\N	2026-02-18 22:18:28+00	2026-02-18 22:18:28+00
13530	4739	4	uncommon	\N	2026-02-18 22:18:28+00	2026-02-18 22:18:28+00
13531	4740	2	uncommon	\N	2026-02-18 22:18:28+00	2026-02-18 22:18:28+00
13532	4740	1	uncommon	\N	2026-02-18 22:18:28+00	2026-02-18 22:18:28+00
13533	4740	3	uncommon	\N	2026-02-18 22:18:28+00	2026-02-18 22:18:28+00
13534	4740	16	uncommon	\N	2026-02-18 22:18:28+00	2026-02-18 22:18:28+00
13535	4740	4	uncommon	\N	2026-02-18 22:18:28+00	2026-02-18 22:18:28+00
13536	4741	27	uncommon	\N	2026-02-18 22:21:10+00	2026-02-18 22:21:10+00
13537	4741	1	uncommon	\N	2026-02-18 22:21:10+00	2026-02-18 22:21:10+00
13538	4741	3	uncommon	\N	2026-02-18 22:21:10+00	2026-02-18 22:21:10+00
13539	4741	4	uncommon	\N	2026-02-18 22:21:10+00	2026-02-18 22:21:10+00
13540	4742	27	uncommon	\N	2026-02-18 22:21:10+00	2026-02-18 22:21:10+00
13541	4742	1	uncommon	\N	2026-02-18 22:21:10+00	2026-02-18 22:21:10+00
13542	4742	3	uncommon	\N	2026-02-18 22:21:10+00	2026-02-18 22:21:10+00
13543	4742	4	uncommon	\N	2026-02-18 22:21:10+00	2026-02-18 22:21:10+00
13544	4743	27	uncommon	\N	2026-02-18 22:21:10+00	2026-02-18 22:21:10+00
13545	4743	1	uncommon	\N	2026-02-18 22:21:10+00	2026-02-18 22:21:10+00
13546	4743	3	uncommon	\N	2026-02-18 22:21:10+00	2026-02-18 22:21:10+00
13547	4743	4	uncommon	\N	2026-02-18 22:21:10+00	2026-02-18 22:21:10+00
13548	4744	27	uncommon	\N	2026-02-18 22:21:10+00	2026-02-18 22:21:10+00
13549	4744	1	uncommon	\N	2026-02-18 22:21:10+00	2026-02-18 22:21:10+00
13550	4744	3	uncommon	\N	2026-02-18 22:21:10+00	2026-02-18 22:21:10+00
13551	4744	4	uncommon	\N	2026-02-18 22:21:10+00	2026-02-18 22:21:10+00
13552	4745	1	uncommon	\N	2026-02-18 22:26:35+00	2026-02-18 22:26:35+00
13553	4746	1	uncommon	\N	2026-02-18 22:26:35+00	2026-02-18 22:26:35+00
13554	4747	1	uncommon	\N	2026-02-18 22:26:35+00	2026-02-18 22:26:35+00
13555	4748	1	uncommon	\N	2026-02-18 22:26:35+00	2026-02-18 22:26:35+00
13556	4749	1	uncommon	\N	2026-02-18 22:26:35+00	2026-02-18 22:26:35+00
13557	4750	1	uncommon	\N	2026-02-18 22:26:35+00	2026-02-18 22:26:35+00
13558	4751	2	uncommon	\N	2026-02-18 22:26:35+00	2026-02-18 22:26:35+00
13559	4752	27	uncommon	\N	2026-02-18 22:26:35+00	2026-02-18 22:26:35+00
13560	4753	27	uncommon	\N	2026-02-18 22:26:35+00	2026-02-18 22:26:35+00
13561	4754	27	uncommon	\N	2026-02-18 22:26:35+00	2026-02-18 22:26:35+00
13562	4755	2	uncommon	\N	2026-02-18 22:28:25+00	2026-02-18 22:28:25+00
13563	4755	3	uncommon	\N	2026-02-18 22:28:25+00	2026-02-18 22:28:25+00
13564	4755	28	uncommon	\N	2026-02-18 22:28:25+00	2026-02-18 22:28:25+00
13565	4755	4	uncommon	\N	2026-02-18 22:28:25+00	2026-02-18 22:28:25+00
13566	4756	2	uncommon	\N	2026-02-18 22:28:25+00	2026-02-18 22:28:25+00
13567	4756	3	uncommon	\N	2026-02-18 22:28:25+00	2026-02-18 22:28:25+00
13568	4756	28	uncommon	\N	2026-02-18 22:28:25+00	2026-02-18 22:28:25+00
13569	4756	4	uncommon	\N	2026-02-18 22:28:25+00	2026-02-18 22:28:25+00
13570	4757	2	uncommon	\N	2026-02-18 22:28:25+00	2026-02-18 22:28:25+00
13571	4757	3	uncommon	\N	2026-02-18 22:28:25+00	2026-02-18 22:28:25+00
13572	4757	28	uncommon	\N	2026-02-18 22:28:25+00	2026-02-18 22:28:25+00
13573	4757	4	uncommon	\N	2026-02-18 22:28:25+00	2026-02-18 22:28:25+00
13574	4758	32	uncommon	\N	2026-02-18 22:28:25+00	2026-02-18 22:28:25+00
13575	4758	2	uncommon	\N	2026-02-18 22:28:25+00	2026-02-18 22:28:25+00
13576	4758	3	uncommon	\N	2026-02-18 22:28:25+00	2026-02-18 22:28:25+00
13577	4758	28	uncommon	\N	2026-02-18 22:28:25+00	2026-02-18 22:28:25+00
13578	4758	4	uncommon	\N	2026-02-18 22:28:25+00	2026-02-18 22:28:25+00
13579	4759	32	uncommon	\N	2026-02-18 22:28:25+00	2026-02-18 22:28:25+00
13580	4759	2	uncommon	\N	2026-02-18 22:28:25+00	2026-02-18 22:28:25+00
13581	4759	3	uncommon	\N	2026-02-18 22:28:25+00	2026-02-18 22:28:25+00
13582	4759	28	uncommon	\N	2026-02-18 22:28:25+00	2026-02-18 22:28:25+00
13583	4759	4	uncommon	\N	2026-02-18 22:28:25+00	2026-02-18 22:28:25+00
13584	4760	32	uncommon	\N	2026-02-18 22:28:25+00	2026-02-18 22:28:25+00
13585	4760	2	uncommon	\N	2026-02-18 22:28:25+00	2026-02-18 22:28:25+00
13586	4760	3	uncommon	\N	2026-02-18 22:28:25+00	2026-02-18 22:28:25+00
13587	4760	28	uncommon	\N	2026-02-18 22:28:25+00	2026-02-18 22:28:25+00
13588	4760	4	uncommon	\N	2026-02-18 22:28:25+00	2026-02-18 22:28:25+00
13601	4764	23	uncommon	\N	2026-02-18 22:33:54+00	2026-02-18 22:33:54+00
13602	4764	36	uncommon	\N	2026-02-18 22:33:54+00	2026-02-18 22:33:54+00
13603	4764	1	uncommon	\N	2026-02-18 22:33:54+00	2026-02-18 22:33:54+00
13604	4764	4	uncommon	\N	2026-02-18 22:33:54+00	2026-02-18 22:33:54+00
13605	4765	23	uncommon	\N	2026-02-18 22:33:54+00	2026-02-18 22:33:54+00
13606	4765	36	uncommon	\N	2026-02-18 22:33:54+00	2026-02-18 22:33:54+00
13607	4765	1	uncommon	\N	2026-02-18 22:33:54+00	2026-02-18 22:33:54+00
13608	4765	4	uncommon	\N	2026-02-18 22:33:54+00	2026-02-18 22:33:54+00
13609	4766	23	uncommon	\N	2026-02-18 22:33:54+00	2026-02-18 22:33:54+00
13610	4766	36	uncommon	\N	2026-02-18 22:33:54+00	2026-02-18 22:33:54+00
13611	4766	1	uncommon	\N	2026-02-18 22:33:54+00	2026-02-18 22:33:54+00
13612	4766	4	uncommon	\N	2026-02-18 22:33:54+00	2026-02-18 22:33:54+00
13613	4767	23	uncommon	\N	2026-02-18 22:34:16+00	2026-02-18 22:34:16+00
13614	4767	27	uncommon	\N	2026-02-18 22:34:16+00	2026-02-18 22:34:16+00
13615	4767	14	uncommon	\N	2026-02-18 22:34:16+00	2026-02-18 22:34:16+00
13616	4767	1	uncommon	\N	2026-02-18 22:34:16+00	2026-02-18 22:34:16+00
13617	4767	28	uncommon	\N	2026-02-18 22:34:16+00	2026-02-18 22:34:16+00
13618	4767	4	uncommon	\N	2026-02-18 22:34:16+00	2026-02-18 22:34:16+00
13619	4768	23	uncommon	\N	2026-02-18 22:34:16+00	2026-02-18 22:34:16+00
13620	4768	27	uncommon	\N	2026-02-18 22:34:16+00	2026-02-18 22:34:16+00
13621	4768	14	uncommon	\N	2026-02-18 22:34:16+00	2026-02-18 22:34:16+00
13622	4768	1	uncommon	\N	2026-02-18 22:34:16+00	2026-02-18 22:34:16+00
13623	4768	28	uncommon	\N	2026-02-18 22:34:16+00	2026-02-18 22:34:16+00
13624	4768	4	uncommon	\N	2026-02-18 22:34:16+00	2026-02-18 22:34:16+00
13625	4769	23	uncommon	\N	2026-02-18 22:34:16+00	2026-02-18 22:34:16+00
13626	4769	27	uncommon	\N	2026-02-18 22:34:16+00	2026-02-18 22:34:16+00
13627	4769	14	uncommon	\N	2026-02-18 22:34:16+00	2026-02-18 22:34:16+00
13628	4769	1	uncommon	\N	2026-02-18 22:34:16+00	2026-02-18 22:34:16+00
13629	4769	28	uncommon	\N	2026-02-18 22:34:16+00	2026-02-18 22:34:16+00
13630	4769	4	uncommon	\N	2026-02-18 22:34:16+00	2026-02-18 22:34:16+00
13631	4770	23	uncommon	\N	2026-02-18 22:34:16+00	2026-02-18 22:34:16+00
13632	4770	27	uncommon	\N	2026-02-18 22:34:16+00	2026-02-18 22:34:16+00
13633	4770	14	uncommon	\N	2026-02-18 22:34:16+00	2026-02-18 22:34:16+00
13634	4770	1	uncommon	\N	2026-02-18 22:34:16+00	2026-02-18 22:34:16+00
13635	4770	28	uncommon	\N	2026-02-18 22:34:16+00	2026-02-18 22:34:16+00
13636	4770	4	uncommon	\N	2026-02-18 22:34:16+00	2026-02-18 22:34:16+00
13637	4771	17	uncommon	\N	2026-02-18 22:35:08+00	2026-02-18 22:35:08+00
13638	4771	18	uncommon	\N	2026-02-18 22:35:08+00	2026-02-18 22:35:08+00
13639	4771	2	uncommon	\N	2026-02-18 22:35:08+00	2026-02-18 22:35:08+00
13640	4771	3	uncommon	\N	2026-02-18 22:35:08+00	2026-02-18 22:35:08+00
13641	4771	16	uncommon	\N	2026-02-18 22:35:08+00	2026-02-18 22:35:08+00
13642	4771	4	uncommon	\N	2026-02-18 22:35:08+00	2026-02-18 22:35:08+00
13643	4772	17	uncommon	\N	2026-02-18 22:35:08+00	2026-02-18 22:35:08+00
13644	4772	18	uncommon	\N	2026-02-18 22:35:08+00	2026-02-18 22:35:08+00
13645	4772	2	uncommon	\N	2026-02-18 22:35:08+00	2026-02-18 22:35:08+00
13646	4772	3	uncommon	\N	2026-02-18 22:35:08+00	2026-02-18 22:35:08+00
13647	4772	16	uncommon	\N	2026-02-18 22:35:08+00	2026-02-18 22:35:08+00
13648	4772	4	uncommon	\N	2026-02-18 22:35:08+00	2026-02-18 22:35:08+00
13649	4773	17	uncommon	\N	2026-02-18 22:35:08+00	2026-02-18 22:35:08+00
13650	4773	18	uncommon	\N	2026-02-18 22:35:08+00	2026-02-18 22:35:08+00
13651	4773	2	uncommon	\N	2026-02-18 22:35:08+00	2026-02-18 22:35:08+00
13652	4773	3	uncommon	\N	2026-02-18 22:35:08+00	2026-02-18 22:35:08+00
13653	4773	16	uncommon	\N	2026-02-18 22:35:08+00	2026-02-18 22:35:08+00
13654	4773	4	uncommon	\N	2026-02-18 22:35:08+00	2026-02-18 22:35:08+00
13655	4774	17	uncommon	\N	2026-02-18 22:35:08+00	2026-02-18 22:35:08+00
13656	4774	18	uncommon	\N	2026-02-18 22:35:08+00	2026-02-18 22:35:08+00
13657	4774	2	uncommon	\N	2026-02-18 22:35:08+00	2026-02-18 22:35:08+00
13658	4774	3	uncommon	\N	2026-02-18 22:35:08+00	2026-02-18 22:35:08+00
13659	4774	16	uncommon	\N	2026-02-18 22:35:08+00	2026-02-18 22:35:08+00
13660	4774	4	uncommon	\N	2026-02-18 22:35:08+00	2026-02-18 22:35:08+00
13661	4775	17	uncommon	\N	2026-02-18 22:35:08+00	2026-02-18 22:35:08+00
13662	4775	18	uncommon	\N	2026-02-18 22:35:08+00	2026-02-18 22:35:08+00
13663	4775	2	uncommon	\N	2026-02-18 22:35:08+00	2026-02-18 22:35:08+00
13664	4775	3	uncommon	\N	2026-02-18 22:35:08+00	2026-02-18 22:35:08+00
13665	4775	16	uncommon	\N	2026-02-18 22:35:08+00	2026-02-18 22:35:08+00
13666	4775	4	uncommon	\N	2026-02-18 22:35:08+00	2026-02-18 22:35:08+00
13667	4776	17	uncommon	\N	2026-02-18 22:35:08+00	2026-02-18 22:35:08+00
13668	4776	18	uncommon	\N	2026-02-18 22:35:08+00	2026-02-18 22:35:08+00
13669	4776	2	uncommon	\N	2026-02-18 22:35:08+00	2026-02-18 22:35:08+00
13670	4776	3	uncommon	\N	2026-02-18 22:35:08+00	2026-02-18 22:35:08+00
13671	4776	16	uncommon	\N	2026-02-18 22:35:08+00	2026-02-18 22:35:08+00
13672	4776	4	uncommon	\N	2026-02-18 22:35:08+00	2026-02-18 22:35:08+00
13673	4777	17	uncommon	\N	2026-02-18 22:35:08+00	2026-02-18 22:35:08+00
13674	4777	18	uncommon	\N	2026-02-18 22:35:08+00	2026-02-18 22:35:08+00
13675	4777	2	uncommon	\N	2026-02-18 22:35:08+00	2026-02-18 22:35:08+00
13676	4777	3	uncommon	\N	2026-02-18 22:35:08+00	2026-02-18 22:35:08+00
13677	4777	16	uncommon	\N	2026-02-18 22:35:08+00	2026-02-18 22:35:08+00
13678	4777	4	uncommon	\N	2026-02-18 22:35:08+00	2026-02-18 22:35:08+00
13679	4778	17	uncommon	\N	2026-02-18 22:35:08+00	2026-02-18 22:35:08+00
13680	4778	18	uncommon	\N	2026-02-18 22:35:08+00	2026-02-18 22:35:08+00
13681	4778	2	uncommon	\N	2026-02-18 22:35:08+00	2026-02-18 22:35:08+00
13682	4778	3	uncommon	\N	2026-02-18 22:35:08+00	2026-02-18 22:35:08+00
13683	4778	16	uncommon	\N	2026-02-18 22:35:08+00	2026-02-18 22:35:08+00
13684	4778	4	uncommon	\N	2026-02-18 22:35:08+00	2026-02-18 22:35:08+00
13685	4779	1	uncommon	\N	2026-02-18 22:36:07+00	2026-02-18 22:36:07+00
13686	4779	28	uncommon	\N	2026-02-18 22:36:07+00	2026-02-18 22:36:07+00
13687	4779	4	uncommon	\N	2026-02-18 22:36:07+00	2026-02-18 22:36:07+00
13688	4780	1	uncommon	\N	2026-02-18 22:36:07+00	2026-02-18 22:36:07+00
13689	4780	28	uncommon	\N	2026-02-18 22:36:07+00	2026-02-18 22:36:07+00
13690	4780	4	uncommon	\N	2026-02-18 22:36:07+00	2026-02-18 22:36:07+00
13691	4781	1	uncommon	\N	2026-02-18 22:36:07+00	2026-02-18 22:36:07+00
13692	4781	28	uncommon	\N	2026-02-18 22:36:07+00	2026-02-18 22:36:07+00
13693	4781	4	uncommon	\N	2026-02-18 22:36:07+00	2026-02-18 22:36:07+00
13694	4782	28	uncommon	\N	2026-02-18 22:36:07+00	2026-02-18 22:36:07+00
13695	4782	4	uncommon	\N	2026-02-18 22:36:07+00	2026-02-18 22:36:07+00
13696	4783	28	uncommon	\N	2026-02-18 22:36:07+00	2026-02-18 22:36:07+00
13697	4783	4	uncommon	\N	2026-02-18 22:36:07+00	2026-02-18 22:36:07+00
13698	4784	28	uncommon	\N	2026-02-18 22:36:07+00	2026-02-18 22:36:07+00
13699	4784	4	uncommon	\N	2026-02-18 22:36:07+00	2026-02-18 22:36:07+00
13700	4785	2	uncommon	\N	2026-02-18 22:38:36+00	2026-02-18 22:38:36+00
13701	4785	1	uncommon	\N	2026-02-18 22:38:36+00	2026-02-18 22:38:36+00
13702	4786	2	uncommon	\N	2026-02-18 22:38:36+00	2026-02-18 22:38:36+00
13703	4786	1	uncommon	\N	2026-02-18 22:38:36+00	2026-02-18 22:38:36+00
13704	4787	2	uncommon	\N	2026-02-18 22:38:36+00	2026-02-18 22:38:36+00
13705	4787	1	uncommon	\N	2026-02-18 22:38:36+00	2026-02-18 22:38:36+00
13706	4788	1	uncommon	\N	2026-02-18 22:38:36+00	2026-02-18 22:38:36+00
13707	4789	2	uncommon	\N	2026-02-18 22:38:36+00	2026-02-18 22:38:36+00
13708	4789	1	uncommon	\N	2026-02-18 22:38:36+00	2026-02-18 22:38:36+00
13709	4789	3	uncommon	\N	2026-02-18 22:38:36+00	2026-02-18 22:38:36+00
13710	4793	23	uncommon	\N	2026-02-18 22:39:09+00	2026-02-18 22:39:09+00
13711	4793	1	uncommon	\N	2026-02-18 22:39:09+00	2026-02-18 22:39:09+00
13712	4793	4	uncommon	\N	2026-02-18 22:39:09+00	2026-02-18 22:39:09+00
13713	4794	23	uncommon	\N	2026-02-18 22:39:09+00	2026-02-18 22:39:09+00
13714	4794	1	uncommon	\N	2026-02-18 22:39:09+00	2026-02-18 22:39:09+00
13715	4794	4	uncommon	\N	2026-02-18 22:39:09+00	2026-02-18 22:39:09+00
13716	4795	23	uncommon	\N	2026-02-18 22:39:09+00	2026-02-18 22:39:09+00
13717	4795	1	uncommon	\N	2026-02-18 22:39:09+00	2026-02-18 22:39:09+00
13718	4795	4	uncommon	\N	2026-02-18 22:39:09+00	2026-02-18 22:39:09+00
13719	4796	23	uncommon	\N	2026-02-18 22:39:42+00	2026-02-18 22:39:42+00
13720	4796	1	uncommon	\N	2026-02-18 22:39:42+00	2026-02-18 22:39:42+00
13721	4796	4	uncommon	\N	2026-02-18 22:39:42+00	2026-02-18 22:39:42+00
13722	4797	23	uncommon	\N	2026-02-18 22:39:42+00	2026-02-18 22:39:42+00
13723	4797	1	uncommon	\N	2026-02-18 22:39:42+00	2026-02-18 22:39:42+00
13724	4797	4	uncommon	\N	2026-02-18 22:39:42+00	2026-02-18 22:39:42+00
13725	4798	23	uncommon	\N	2026-02-18 22:39:42+00	2026-02-18 22:39:42+00
13726	4798	1	uncommon	\N	2026-02-18 22:39:42+00	2026-02-18 22:39:42+00
13727	4798	4	uncommon	\N	2026-02-18 22:39:42+00	2026-02-18 22:39:42+00
13728	4799	23	uncommon	\N	2026-02-18 22:40:14+00	2026-02-18 22:40:14+00
13729	4800	23	uncommon	\N	2026-02-18 22:40:14+00	2026-02-18 22:40:14+00
13730	4801	23	uncommon	\N	2026-02-18 22:40:14+00	2026-02-18 22:40:14+00
13731	4802	23	uncommon	\N	2026-02-18 22:40:14+00	2026-02-18 22:40:14+00
13732	4803	35	uncommon	\N	2026-02-18 22:40:45+00	2026-02-18 22:40:45+00
13733	4803	1	uncommon	\N	2026-02-18 22:40:45+00	2026-02-18 22:40:45+00
13734	4803	4	uncommon	\N	2026-02-18 22:40:45+00	2026-02-18 22:40:45+00
13735	4803	34	uncommon	\N	2026-02-18 22:40:45+00	2026-02-18 22:40:45+00
13736	4804	35	uncommon	\N	2026-02-18 22:40:45+00	2026-02-18 22:40:45+00
13737	4804	1	uncommon	\N	2026-02-18 22:40:45+00	2026-02-18 22:40:45+00
13738	4804	4	uncommon	\N	2026-02-18 22:40:45+00	2026-02-18 22:40:45+00
13739	4804	34	uncommon	\N	2026-02-18 22:40:45+00	2026-02-18 22:40:45+00
13740	4805	35	uncommon	\N	2026-02-18 22:40:45+00	2026-02-18 22:40:45+00
13741	4805	1	uncommon	\N	2026-02-18 22:40:45+00	2026-02-18 22:40:45+00
13742	4805	4	uncommon	\N	2026-02-18 22:40:45+00	2026-02-18 22:40:45+00
13743	4805	34	uncommon	\N	2026-02-18 22:40:45+00	2026-02-18 22:40:45+00
13744	4806	23	uncommon	\N	2026-02-18 22:41:16+00	2026-02-18 22:41:16+00
13745	4806	2	uncommon	\N	2026-02-18 22:41:16+00	2026-02-18 22:41:16+00
13746	4806	1	uncommon	\N	2026-02-18 22:41:16+00	2026-02-18 22:41:16+00
13747	4806	3	uncommon	\N	2026-02-18 22:41:16+00	2026-02-18 22:41:16+00
13748	4806	28	uncommon	\N	2026-02-18 22:41:16+00	2026-02-18 22:41:16+00
13749	4806	4	uncommon	\N	2026-02-18 22:41:16+00	2026-02-18 22:41:16+00
13750	4807	23	uncommon	\N	2026-02-18 22:41:16+00	2026-02-18 22:41:16+00
13751	4807	2	uncommon	\N	2026-02-18 22:41:16+00	2026-02-18 22:41:16+00
13752	4807	1	uncommon	\N	2026-02-18 22:41:16+00	2026-02-18 22:41:16+00
13753	4807	3	uncommon	\N	2026-02-18 22:41:16+00	2026-02-18 22:41:16+00
13754	4807	28	uncommon	\N	2026-02-18 22:41:16+00	2026-02-18 22:41:16+00
13755	4807	4	uncommon	\N	2026-02-18 22:41:16+00	2026-02-18 22:41:16+00
13756	4808	23	uncommon	\N	2026-02-18 22:41:16+00	2026-02-18 22:41:16+00
13757	4808	2	uncommon	\N	2026-02-18 22:41:16+00	2026-02-18 22:41:16+00
13758	4808	1	uncommon	\N	2026-02-18 22:41:16+00	2026-02-18 22:41:16+00
13759	4808	3	uncommon	\N	2026-02-18 22:41:16+00	2026-02-18 22:41:16+00
13760	4808	28	uncommon	\N	2026-02-18 22:41:16+00	2026-02-18 22:41:16+00
13761	4808	4	uncommon	\N	2026-02-18 22:41:16+00	2026-02-18 22:41:16+00
13762	4809	23	uncommon	\N	2026-02-18 22:41:16+00	2026-02-18 22:41:16+00
13763	4809	2	uncommon	\N	2026-02-18 22:41:16+00	2026-02-18 22:41:16+00
13764	4809	1	uncommon	\N	2026-02-18 22:41:16+00	2026-02-18 22:41:16+00
13765	4809	3	uncommon	\N	2026-02-18 22:41:16+00	2026-02-18 22:41:16+00
13766	4809	28	uncommon	\N	2026-02-18 22:41:16+00	2026-02-18 22:41:16+00
13767	4809	4	uncommon	\N	2026-02-18 22:41:16+00	2026-02-18 22:41:16+00
13768	4810	27	uncommon	\N	2026-02-18 22:42:10+00	2026-02-18 22:42:10+00
13769	4810	1	uncommon	\N	2026-02-18 22:42:10+00	2026-02-18 22:42:10+00
13770	4810	3	uncommon	\N	2026-02-18 22:42:10+00	2026-02-18 22:42:10+00
13771	4810	16	uncommon	\N	2026-02-18 22:42:10+00	2026-02-18 22:42:10+00
13772	4810	4	uncommon	\N	2026-02-18 22:42:10+00	2026-02-18 22:42:10+00
13773	4811	27	uncommon	\N	2026-02-18 22:42:10+00	2026-02-18 22:42:10+00
13774	4811	1	uncommon	\N	2026-02-18 22:42:10+00	2026-02-18 22:42:10+00
13775	4811	3	uncommon	\N	2026-02-18 22:42:10+00	2026-02-18 22:42:10+00
13776	4811	16	uncommon	\N	2026-02-18 22:42:10+00	2026-02-18 22:42:10+00
13777	4811	4	uncommon	\N	2026-02-18 22:42:10+00	2026-02-18 22:42:10+00
13778	4812	27	uncommon	\N	2026-02-18 22:42:10+00	2026-02-18 22:42:10+00
13779	4812	1	uncommon	\N	2026-02-18 22:42:10+00	2026-02-18 22:42:10+00
13780	4812	3	uncommon	\N	2026-02-18 22:42:10+00	2026-02-18 22:42:10+00
13781	4812	16	uncommon	\N	2026-02-18 22:42:10+00	2026-02-18 22:42:10+00
13782	4812	4	uncommon	\N	2026-02-18 22:42:10+00	2026-02-18 22:42:10+00
13783	4813	2	uncommon	\N	2026-02-18 22:42:40+00	2026-02-18 22:42:40+00
13784	4813	1	uncommon	\N	2026-02-18 22:42:40+00	2026-02-18 22:42:40+00
13785	4813	3	uncommon	\N	2026-02-18 22:42:40+00	2026-02-18 22:42:40+00
13786	4813	4	uncommon	\N	2026-02-18 22:42:40+00	2026-02-18 22:42:40+00
13787	4814	35	uncommon	\N	2026-02-18 22:42:40+00	2026-02-18 22:42:40+00
13788	4814	2	uncommon	\N	2026-02-18 22:42:40+00	2026-02-18 22:42:40+00
13789	4814	1	uncommon	\N	2026-02-18 22:42:40+00	2026-02-18 22:42:40+00
13790	4814	3	uncommon	\N	2026-02-18 22:42:40+00	2026-02-18 22:42:40+00
13791	4814	4	uncommon	\N	2026-02-18 22:42:40+00	2026-02-18 22:42:40+00
13792	4815	35	uncommon	\N	2026-02-18 22:42:40+00	2026-02-18 22:42:40+00
13793	4815	2	uncommon	\N	2026-02-18 22:42:40+00	2026-02-18 22:42:40+00
13794	4815	1	uncommon	\N	2026-02-18 22:42:40+00	2026-02-18 22:42:40+00
13795	4815	3	uncommon	\N	2026-02-18 22:42:40+00	2026-02-18 22:42:40+00
13796	4815	4	uncommon	\N	2026-02-18 22:42:40+00	2026-02-18 22:42:40+00
13797	4815	34	uncommon	\N	2026-02-18 22:42:40+00	2026-02-18 22:42:40+00
13798	4816	2	uncommon	\N	2026-02-18 22:42:40+00	2026-02-18 22:42:40+00
13799	4816	1	uncommon	\N	2026-02-18 22:42:40+00	2026-02-18 22:42:40+00
13800	4816	3	uncommon	\N	2026-02-18 22:42:40+00	2026-02-18 22:42:40+00
13801	4816	4	uncommon	\N	2026-02-18 22:42:40+00	2026-02-18 22:42:40+00
13802	4816	34	uncommon	\N	2026-02-18 22:42:40+00	2026-02-18 22:42:40+00
13803	4817	24	uncommon	\N	2026-02-18 22:43:25+00	2026-02-18 22:43:25+00
13804	4817	23	uncommon	\N	2026-02-18 22:43:25+00	2026-02-18 22:43:25+00
13805	4817	36	uncommon	\N	2026-02-18 22:43:25+00	2026-02-18 22:43:25+00
13806	4817	1	uncommon	\N	2026-02-18 22:43:25+00	2026-02-18 22:43:25+00
13807	4818	24	uncommon	\N	2026-02-18 22:43:25+00	2026-02-18 22:43:25+00
13808	4818	23	uncommon	\N	2026-02-18 22:43:25+00	2026-02-18 22:43:25+00
13809	4818	36	uncommon	\N	2026-02-18 22:43:25+00	2026-02-18 22:43:25+00
13810	4818	1	uncommon	\N	2026-02-18 22:43:25+00	2026-02-18 22:43:25+00
13811	4819	24	uncommon	\N	2026-02-18 22:43:25+00	2026-02-18 22:43:25+00
13812	4819	23	uncommon	\N	2026-02-18 22:43:25+00	2026-02-18 22:43:25+00
13813	4819	36	uncommon	\N	2026-02-18 22:43:25+00	2026-02-18 22:43:25+00
13814	4819	1	uncommon	\N	2026-02-18 22:43:25+00	2026-02-18 22:43:25+00
13815	4820	24	uncommon	\N	2026-02-18 22:43:25+00	2026-02-18 22:43:25+00
13816	4820	23	uncommon	\N	2026-02-18 22:43:25+00	2026-02-18 22:43:25+00
13817	4820	36	uncommon	\N	2026-02-18 22:43:25+00	2026-02-18 22:43:25+00
13818	4820	1	uncommon	\N	2026-02-18 22:43:25+00	2026-02-18 22:43:25+00
13819	4821	23	uncommon	\N	2026-02-18 22:43:25+00	2026-02-18 22:43:25+00
13820	4821	2	uncommon	\N	2026-02-18 22:43:25+00	2026-02-18 22:43:25+00
13821	4821	3	uncommon	\N	2026-02-18 22:43:25+00	2026-02-18 22:43:25+00
13822	4822	23	uncommon	\N	2026-02-18 22:43:25+00	2026-02-18 22:43:25+00
13823	4822	2	uncommon	\N	2026-02-18 22:43:25+00	2026-02-18 22:43:25+00
13824	4822	3	uncommon	\N	2026-02-18 22:43:25+00	2026-02-18 22:43:25+00
13825	4823	23	uncommon	\N	2026-02-18 22:43:25+00	2026-02-18 22:43:25+00
13826	4823	2	uncommon	\N	2026-02-18 22:43:25+00	2026-02-18 22:43:25+00
13827	4823	3	uncommon	\N	2026-02-18 22:43:25+00	2026-02-18 22:43:25+00
13828	4824	23	uncommon	\N	2026-02-18 22:43:54+00	2026-02-18 22:43:54+00
13829	4824	1	uncommon	\N	2026-02-18 22:43:54+00	2026-02-18 22:43:54+00
13830	4824	3	uncommon	\N	2026-02-18 22:43:54+00	2026-02-18 22:43:54+00
13831	4824	4	uncommon	\N	2026-02-18 22:43:54+00	2026-02-18 22:43:54+00
13832	4825	23	uncommon	\N	2026-02-18 22:43:54+00	2026-02-18 22:43:54+00
13833	4825	1	uncommon	\N	2026-02-18 22:43:54+00	2026-02-18 22:43:54+00
13834	4825	3	uncommon	\N	2026-02-18 22:43:54+00	2026-02-18 22:43:54+00
13835	4825	4	uncommon	\N	2026-02-18 22:43:54+00	2026-02-18 22:43:54+00
13836	4826	23	uncommon	\N	2026-02-18 22:43:54+00	2026-02-18 22:43:54+00
13837	4826	1	uncommon	\N	2026-02-18 22:43:54+00	2026-02-18 22:43:54+00
13838	4826	3	uncommon	\N	2026-02-18 22:43:54+00	2026-02-18 22:43:54+00
13839	4826	4	uncommon	\N	2026-02-18 22:43:54+00	2026-02-18 22:43:54+00
13840	4827	23	uncommon	\N	2026-02-18 22:43:54+00	2026-02-18 22:43:54+00
13841	4827	3	uncommon	\N	2026-02-18 22:43:54+00	2026-02-18 22:43:54+00
13842	4827	4	uncommon	\N	2026-02-18 22:43:54+00	2026-02-18 22:43:54+00
13843	4828	23	uncommon	\N	2026-02-18 22:43:54+00	2026-02-18 22:43:54+00
13844	4828	3	uncommon	\N	2026-02-18 22:43:54+00	2026-02-18 22:43:54+00
13845	4828	4	uncommon	\N	2026-02-18 22:43:54+00	2026-02-18 22:43:54+00
13846	4829	23	uncommon	\N	2026-02-18 22:44:56+00	2026-02-18 22:44:56+00
13847	4829	1	uncommon	\N	2026-02-18 22:44:56+00	2026-02-18 22:44:56+00
13848	4829	4	uncommon	\N	2026-02-18 22:44:56+00	2026-02-18 22:44:56+00
13849	4830	23	uncommon	\N	2026-02-18 22:44:56+00	2026-02-18 22:44:56+00
13850	4830	1	uncommon	\N	2026-02-18 22:44:56+00	2026-02-18 22:44:56+00
13851	4830	4	uncommon	\N	2026-02-18 22:44:56+00	2026-02-18 22:44:56+00
13852	4831	23	uncommon	\N	2026-02-18 22:44:56+00	2026-02-18 22:44:56+00
13853	4831	1	uncommon	\N	2026-02-18 22:44:56+00	2026-02-18 22:44:56+00
13854	4831	4	uncommon	\N	2026-02-18 22:44:56+00	2026-02-18 22:44:56+00
13855	4832	2	uncommon	\N	2026-02-18 22:45:43+00	2026-02-18 22:45:43+00
13856	4832	1	uncommon	\N	2026-02-18 22:45:43+00	2026-02-18 22:45:43+00
13857	4832	3	uncommon	\N	2026-02-18 22:45:43+00	2026-02-18 22:45:43+00
13858	4832	4	uncommon	\N	2026-02-18 22:45:43+00	2026-02-18 22:45:43+00
13859	4833	2	uncommon	\N	2026-02-18 22:45:43+00	2026-02-18 22:45:43+00
13860	4833	1	uncommon	\N	2026-02-18 22:45:43+00	2026-02-18 22:45:43+00
13861	4833	3	uncommon	\N	2026-02-18 22:45:43+00	2026-02-18 22:45:43+00
13862	4833	4	uncommon	\N	2026-02-18 22:45:43+00	2026-02-18 22:45:43+00
13863	4834	2	uncommon	\N	2026-02-18 22:45:43+00	2026-02-18 22:45:43+00
13864	4834	1	uncommon	\N	2026-02-18 22:45:43+00	2026-02-18 22:45:43+00
13865	4834	3	uncommon	\N	2026-02-18 22:45:43+00	2026-02-18 22:45:43+00
13866	4834	4	uncommon	\N	2026-02-18 22:45:43+00	2026-02-18 22:45:43+00
13867	4835	2	uncommon	\N	2026-02-18 22:45:43+00	2026-02-18 22:45:43+00
13868	4835	3	uncommon	\N	2026-02-18 22:45:43+00	2026-02-18 22:45:43+00
13869	4835	4	uncommon	\N	2026-02-18 22:45:43+00	2026-02-18 22:45:43+00
13870	4836	2	uncommon	\N	2026-02-18 22:45:43+00	2026-02-18 22:45:43+00
13871	4836	3	uncommon	\N	2026-02-18 22:45:43+00	2026-02-18 22:45:43+00
13872	4836	4	uncommon	\N	2026-02-18 22:45:43+00	2026-02-18 22:45:43+00
13873	4837	27	uncommon	\N	2026-02-18 22:45:43+00	2026-02-18 22:45:43+00
13874	4838	27	uncommon	\N	2026-02-18 22:45:43+00	2026-02-18 22:45:43+00
13875	4839	27	uncommon	\N	2026-02-18 22:45:43+00	2026-02-18 22:45:43+00
13876	4840	2	uncommon	\N	2026-02-18 22:45:43+00	2026-02-18 22:45:43+00
13877	4840	3	uncommon	\N	2026-02-18 22:45:43+00	2026-02-18 22:45:43+00
13878	4840	4	uncommon	\N	2026-02-18 22:45:43+00	2026-02-18 22:45:43+00
13879	4841	2	uncommon	\N	2026-02-18 22:45:43+00	2026-02-18 22:45:43+00
13880	4841	3	uncommon	\N	2026-02-18 22:45:43+00	2026-02-18 22:45:43+00
13881	4841	4	uncommon	\N	2026-02-18 22:45:43+00	2026-02-18 22:45:43+00
13882	4842	27	uncommon	\N	2026-02-18 22:46:25+00	2026-02-18 22:46:25+00
13883	4842	1	uncommon	\N	2026-02-18 22:46:25+00	2026-02-18 22:46:25+00
13884	4842	4	uncommon	\N	2026-02-18 22:46:25+00	2026-02-18 22:46:25+00
13885	4843	27	uncommon	\N	2026-02-18 22:46:25+00	2026-02-18 22:46:25+00
13886	4843	1	uncommon	\N	2026-02-18 22:46:25+00	2026-02-18 22:46:25+00
13887	4843	4	uncommon	\N	2026-02-18 22:46:25+00	2026-02-18 22:46:25+00
13888	4844	27	uncommon	\N	2026-02-18 22:46:25+00	2026-02-18 22:46:25+00
13889	4844	1	uncommon	\N	2026-02-18 22:46:25+00	2026-02-18 22:46:25+00
13890	4844	4	uncommon	\N	2026-02-18 22:46:25+00	2026-02-18 22:46:25+00
13891	4845	27	uncommon	\N	2026-02-18 22:46:25+00	2026-02-18 22:46:25+00
13892	4845	1	uncommon	\N	2026-02-18 22:46:25+00	2026-02-18 22:46:25+00
13893	4845	4	uncommon	\N	2026-02-18 22:46:25+00	2026-02-18 22:46:25+00
13894	4846	27	uncommon	\N	2026-02-18 22:46:25+00	2026-02-18 22:46:25+00
13895	4846	1	uncommon	\N	2026-02-18 22:46:25+00	2026-02-18 22:46:25+00
13896	4846	4	uncommon	\N	2026-02-18 22:46:25+00	2026-02-18 22:46:25+00
13897	4847	27	uncommon	\N	2026-02-18 22:46:25+00	2026-02-18 22:46:25+00
13898	4847	32	uncommon	\N	2026-02-18 22:46:25+00	2026-02-18 22:46:25+00
13899	4847	25	uncommon	\N	2026-02-18 22:46:25+00	2026-02-18 22:46:25+00
13900	4847	4	uncommon	\N	2026-02-18 22:46:25+00	2026-02-18 22:46:25+00
13901	4848	27	uncommon	\N	2026-02-18 22:46:25+00	2026-02-18 22:46:25+00
13902	4848	32	uncommon	\N	2026-02-18 22:46:25+00	2026-02-18 22:46:25+00
13903	4848	25	uncommon	\N	2026-02-18 22:46:25+00	2026-02-18 22:46:25+00
13904	4848	4	uncommon	\N	2026-02-18 22:46:25+00	2026-02-18 22:46:25+00
13905	4849	27	uncommon	\N	2026-02-18 22:46:25+00	2026-02-18 22:46:25+00
13906	4849	32	uncommon	\N	2026-02-18 22:46:25+00	2026-02-18 22:46:25+00
13907	4849	25	uncommon	\N	2026-02-18 22:46:25+00	2026-02-18 22:46:25+00
13908	4849	4	uncommon	\N	2026-02-18 22:46:25+00	2026-02-18 22:46:25+00
13909	4850	27	uncommon	\N	2026-02-18 22:47:02+00	2026-02-18 22:47:02+00
13910	4850	32	uncommon	\N	2026-02-18 22:47:02+00	2026-02-18 22:47:02+00
13911	4850	25	uncommon	\N	2026-02-18 22:47:02+00	2026-02-18 22:47:02+00
13912	4850	2	uncommon	\N	2026-02-18 22:47:02+00	2026-02-18 22:47:02+00
13913	4850	1	uncommon	\N	2026-02-18 22:47:02+00	2026-02-18 22:47:02+00
13914	4850	3	uncommon	\N	2026-02-18 22:47:02+00	2026-02-18 22:47:02+00
13915	4850	28	uncommon	\N	2026-02-18 22:47:02+00	2026-02-18 22:47:02+00
13916	4850	4	uncommon	\N	2026-02-18 22:47:02+00	2026-02-18 22:47:02+00
13917	4851	27	uncommon	\N	2026-02-18 22:47:02+00	2026-02-18 22:47:02+00
13918	4851	32	uncommon	\N	2026-02-18 22:47:02+00	2026-02-18 22:47:02+00
13919	4851	25	uncommon	\N	2026-02-18 22:47:02+00	2026-02-18 22:47:02+00
13920	4851	2	uncommon	\N	2026-02-18 22:47:02+00	2026-02-18 22:47:02+00
13921	4851	1	uncommon	\N	2026-02-18 22:47:02+00	2026-02-18 22:47:02+00
13922	4851	3	uncommon	\N	2026-02-18 22:47:02+00	2026-02-18 22:47:02+00
13923	4851	28	uncommon	\N	2026-02-18 22:47:02+00	2026-02-18 22:47:02+00
13924	4851	4	uncommon	\N	2026-02-18 22:47:02+00	2026-02-18 22:47:02+00
13925	4852	27	uncommon	\N	2026-02-18 22:47:02+00	2026-02-18 22:47:02+00
13926	4852	32	uncommon	\N	2026-02-18 22:47:02+00	2026-02-18 22:47:02+00
13927	4852	25	uncommon	\N	2026-02-18 22:47:02+00	2026-02-18 22:47:02+00
13928	4852	2	uncommon	\N	2026-02-18 22:47:02+00	2026-02-18 22:47:02+00
13929	4852	1	uncommon	\N	2026-02-18 22:47:02+00	2026-02-18 22:47:02+00
13930	4852	3	uncommon	\N	2026-02-18 22:47:02+00	2026-02-18 22:47:02+00
13931	4852	28	uncommon	\N	2026-02-18 22:47:02+00	2026-02-18 22:47:02+00
13932	4852	4	uncommon	\N	2026-02-18 22:47:02+00	2026-02-18 22:47:02+00
13933	4853	27	uncommon	\N	2026-02-18 22:47:02+00	2026-02-18 22:47:02+00
13934	4853	32	uncommon	\N	2026-02-18 22:47:02+00	2026-02-18 22:47:02+00
13935	4853	25	uncommon	\N	2026-02-18 22:47:02+00	2026-02-18 22:47:02+00
13936	4853	2	uncommon	\N	2026-02-18 22:47:02+00	2026-02-18 22:47:02+00
13937	4853	1	uncommon	\N	2026-02-18 22:47:02+00	2026-02-18 22:47:02+00
13938	4853	3	uncommon	\N	2026-02-18 22:47:02+00	2026-02-18 22:47:02+00
13939	4853	28	uncommon	\N	2026-02-18 22:47:02+00	2026-02-18 22:47:02+00
13940	4853	4	uncommon	\N	2026-02-18 22:47:02+00	2026-02-18 22:47:02+00
13941	4854	25	uncommon	\N	2026-02-18 22:47:28+00	2026-02-18 22:47:28+00
13942	4854	2	uncommon	\N	2026-02-18 22:47:28+00	2026-02-18 22:47:28+00
13943	4854	1	uncommon	\N	2026-02-18 22:47:28+00	2026-02-18 22:47:28+00
13944	4854	3	uncommon	\N	2026-02-18 22:47:28+00	2026-02-18 22:47:28+00
13945	4854	4	uncommon	\N	2026-02-18 22:47:28+00	2026-02-18 22:47:28+00
13946	4855	25	uncommon	\N	2026-02-18 22:47:28+00	2026-02-18 22:47:28+00
13947	4855	2	uncommon	\N	2026-02-18 22:47:28+00	2026-02-18 22:47:28+00
13948	4855	1	uncommon	\N	2026-02-18 22:47:28+00	2026-02-18 22:47:28+00
13949	4855	3	uncommon	\N	2026-02-18 22:47:28+00	2026-02-18 22:47:28+00
13950	4855	4	uncommon	\N	2026-02-18 22:47:28+00	2026-02-18 22:47:28+00
13951	4855	37	uncommon	\N	2026-02-18 22:47:28+00	2026-02-18 22:47:28+00
13952	4856	25	uncommon	\N	2026-02-18 22:47:28+00	2026-02-18 22:47:28+00
13953	4856	2	uncommon	\N	2026-02-18 22:47:28+00	2026-02-18 22:47:28+00
13954	4856	1	uncommon	\N	2026-02-18 22:47:28+00	2026-02-18 22:47:28+00
13955	4856	3	uncommon	\N	2026-02-18 22:47:28+00	2026-02-18 22:47:28+00
13956	4856	4	uncommon	\N	2026-02-18 22:47:28+00	2026-02-18 22:47:28+00
13957	4856	37	uncommon	\N	2026-02-18 22:47:28+00	2026-02-18 22:47:28+00
13958	4858	25	uncommon	\N	2026-02-18 22:47:28+00	2026-02-18 22:47:28+00
13959	4858	2	uncommon	\N	2026-02-18 22:47:28+00	2026-02-18 22:47:28+00
13960	4858	3	uncommon	\N	2026-02-18 22:47:28+00	2026-02-18 22:47:28+00
13961	4858	4	uncommon	\N	2026-02-18 22:47:28+00	2026-02-18 22:47:28+00
13962	4858	37	uncommon	\N	2026-02-18 22:47:28+00	2026-02-18 22:47:28+00
13963	4859	25	uncommon	\N	2026-02-18 22:47:28+00	2026-02-18 22:47:28+00
13964	4859	2	uncommon	\N	2026-02-18 22:47:28+00	2026-02-18 22:47:28+00
13965	4859	3	uncommon	\N	2026-02-18 22:47:28+00	2026-02-18 22:47:28+00
13966	4859	4	uncommon	\N	2026-02-18 22:47:28+00	2026-02-18 22:47:28+00
13967	4859	37	uncommon	\N	2026-02-18 22:47:28+00	2026-02-18 22:47:28+00
13968	4860	25	uncommon	\N	2026-02-18 22:47:28+00	2026-02-18 22:47:28+00
13969	4860	2	uncommon	\N	2026-02-18 22:47:28+00	2026-02-18 22:47:28+00
13970	4860	3	uncommon	\N	2026-02-18 22:47:28+00	2026-02-18 22:47:28+00
13971	4860	4	uncommon	\N	2026-02-18 22:47:28+00	2026-02-18 22:47:28+00
13972	4860	37	uncommon	\N	2026-02-18 22:47:28+00	2026-02-18 22:47:28+00
13973	4861	25	uncommon	\N	2026-02-18 22:47:28+00	2026-02-18 22:47:28+00
13974	4861	2	uncommon	\N	2026-02-18 22:47:28+00	2026-02-18 22:47:28+00
13975	4861	3	uncommon	\N	2026-02-18 22:47:28+00	2026-02-18 22:47:28+00
13976	4861	4	uncommon	\N	2026-02-18 22:47:28+00	2026-02-18 22:47:28+00
13977	4861	37	uncommon	\N	2026-02-18 22:47:28+00	2026-02-18 22:47:28+00
13978	4862	17	uncommon	\N	2026-02-18 22:48:30+00	2026-02-18 22:48:30+00
13979	4862	2	uncommon	\N	2026-02-18 22:48:30+00	2026-02-18 22:48:30+00
13980	4863	17	uncommon	\N	2026-02-18 22:48:30+00	2026-02-18 22:48:30+00
13981	4863	2	uncommon	\N	2026-02-18 22:48:30+00	2026-02-18 22:48:30+00
13982	4863	33	uncommon	\N	2026-02-18 22:48:30+00	2026-02-18 22:48:30+00
13983	4864	17	uncommon	\N	2026-02-18 22:48:30+00	2026-02-18 22:48:30+00
13984	4864	32	uncommon	\N	2026-02-18 22:48:30+00	2026-02-18 22:48:30+00
13985	4864	2	uncommon	\N	2026-02-18 22:48:30+00	2026-02-18 22:48:30+00
13986	4864	33	uncommon	\N	2026-02-18 22:48:30+00	2026-02-18 22:48:30+00
13987	4865	17	uncommon	\N	2026-02-18 22:48:30+00	2026-02-18 22:48:30+00
13988	4865	2	uncommon	\N	2026-02-18 22:48:30+00	2026-02-18 22:48:30+00
13989	4865	33	uncommon	\N	2026-02-18 22:48:30+00	2026-02-18 22:48:30+00
13990	4866	17	uncommon	\N	2026-02-18 22:48:30+00	2026-02-18 22:48:30+00
13991	4866	18	uncommon	\N	2026-02-18 22:48:30+00	2026-02-18 22:48:30+00
13992	4866	20	uncommon	\N	2026-02-18 22:48:30+00	2026-02-18 22:48:30+00
13993	4866	32	uncommon	\N	2026-02-18 22:48:30+00	2026-02-18 22:48:30+00
13994	4866	25	uncommon	\N	2026-02-18 22:48:30+00	2026-02-18 22:48:30+00
13995	4866	2	uncommon	\N	2026-02-18 22:48:30+00	2026-02-18 22:48:30+00
13996	4866	33	uncommon	\N	2026-02-18 22:48:30+00	2026-02-18 22:48:30+00
13997	4867	17	uncommon	\N	2026-02-18 22:48:30+00	2026-02-18 22:48:30+00
13998	4867	18	uncommon	\N	2026-02-18 22:48:30+00	2026-02-18 22:48:30+00
13999	4867	20	uncommon	\N	2026-02-18 22:48:30+00	2026-02-18 22:48:30+00
14000	4867	32	uncommon	\N	2026-02-18 22:48:30+00	2026-02-18 22:48:30+00
14001	4867	25	uncommon	\N	2026-02-18 22:48:30+00	2026-02-18 22:48:30+00
14002	4867	2	uncommon	\N	2026-02-18 22:48:30+00	2026-02-18 22:48:30+00
14003	4867	33	uncommon	\N	2026-02-18 22:48:30+00	2026-02-18 22:48:30+00
14004	4868	23	uncommon	\N	2026-02-18 22:49:04+00	2026-02-18 22:49:04+00
14005	4868	2	uncommon	\N	2026-02-18 22:49:04+00	2026-02-18 22:49:04+00
14006	4868	28	uncommon	\N	2026-02-18 22:49:04+00	2026-02-18 22:49:04+00
14007	4868	4	uncommon	\N	2026-02-18 22:49:04+00	2026-02-18 22:49:04+00
14008	4869	23	uncommon	\N	2026-02-18 22:49:04+00	2026-02-18 22:49:04+00
14009	4869	2	uncommon	\N	2026-02-18 22:49:04+00	2026-02-18 22:49:04+00
14010	4869	28	uncommon	\N	2026-02-18 22:49:04+00	2026-02-18 22:49:04+00
14011	4869	4	uncommon	\N	2026-02-18 22:49:04+00	2026-02-18 22:49:04+00
14012	4870	23	uncommon	\N	2026-02-18 22:49:04+00	2026-02-18 22:49:04+00
14013	4870	2	uncommon	\N	2026-02-18 22:49:04+00	2026-02-18 22:49:04+00
14014	4870	28	uncommon	\N	2026-02-18 22:49:04+00	2026-02-18 22:49:04+00
14015	4870	4	uncommon	\N	2026-02-18 22:49:04+00	2026-02-18 22:49:04+00
14016	4871	24	uncommon	\N	2026-02-18 22:49:33+00	2026-02-18 22:49:33+00
14017	4871	1	uncommon	\N	2026-02-18 22:49:33+00	2026-02-18 22:49:33+00
14018	4871	3	uncommon	\N	2026-02-18 22:49:33+00	2026-02-18 22:49:33+00
14019	4871	4	uncommon	\N	2026-02-18 22:49:33+00	2026-02-18 22:49:33+00
14020	4872	24	uncommon	\N	2026-02-18 22:49:33+00	2026-02-18 22:49:33+00
14021	4872	1	uncommon	\N	2026-02-18 22:49:33+00	2026-02-18 22:49:33+00
14022	4872	3	uncommon	\N	2026-02-18 22:49:33+00	2026-02-18 22:49:33+00
14023	4872	4	uncommon	\N	2026-02-18 22:49:33+00	2026-02-18 22:49:33+00
14024	4873	24	uncommon	\N	2026-02-18 22:49:33+00	2026-02-18 22:49:33+00
14025	4873	1	uncommon	\N	2026-02-18 22:49:33+00	2026-02-18 22:49:33+00
14026	4873	3	uncommon	\N	2026-02-18 22:49:33+00	2026-02-18 22:49:33+00
14027	4873	4	uncommon	\N	2026-02-18 22:49:33+00	2026-02-18 22:49:33+00
14028	4874	24	uncommon	\N	2026-02-18 22:49:33+00	2026-02-18 22:49:33+00
14029	4874	3	uncommon	\N	2026-02-18 22:49:33+00	2026-02-18 22:49:33+00
14030	4874	4	uncommon	\N	2026-02-18 22:49:33+00	2026-02-18 22:49:33+00
14031	4875	24	uncommon	\N	2026-02-18 22:49:33+00	2026-02-18 22:49:33+00
14032	4875	3	uncommon	\N	2026-02-18 22:49:33+00	2026-02-18 22:49:33+00
14033	4875	4	uncommon	\N	2026-02-18 22:49:33+00	2026-02-18 22:49:33+00
14034	4876	24	uncommon	\N	2026-02-18 22:49:33+00	2026-02-18 22:49:33+00
14035	4876	3	uncommon	\N	2026-02-18 22:49:33+00	2026-02-18 22:49:33+00
14036	4876	4	uncommon	\N	2026-02-18 22:49:33+00	2026-02-18 22:49:33+00
14037	4877	32	uncommon	\N	2026-02-18 22:50:10+00	2026-02-18 22:50:10+00
14038	4877	25	uncommon	\N	2026-02-18 22:50:10+00	2026-02-18 22:50:10+00
14039	4877	2	uncommon	\N	2026-02-18 22:50:10+00	2026-02-18 22:50:10+00
14040	4877	1	uncommon	\N	2026-02-18 22:50:10+00	2026-02-18 22:50:10+00
14041	4877	3	uncommon	\N	2026-02-18 22:50:10+00	2026-02-18 22:50:10+00
14042	4877	4	uncommon	\N	2026-02-18 22:50:10+00	2026-02-18 22:50:10+00
14043	4878	32	uncommon	\N	2026-02-18 22:50:10+00	2026-02-18 22:50:10+00
14044	4878	25	uncommon	\N	2026-02-18 22:50:10+00	2026-02-18 22:50:10+00
14045	4878	2	uncommon	\N	2026-02-18 22:50:10+00	2026-02-18 22:50:10+00
14046	4878	1	uncommon	\N	2026-02-18 22:50:10+00	2026-02-18 22:50:10+00
14047	4878	3	uncommon	\N	2026-02-18 22:50:10+00	2026-02-18 22:50:10+00
14048	4878	4	uncommon	\N	2026-02-18 22:50:10+00	2026-02-18 22:50:10+00
14049	4879	32	uncommon	\N	2026-02-18 22:50:10+00	2026-02-18 22:50:10+00
14050	4879	25	uncommon	\N	2026-02-18 22:50:10+00	2026-02-18 22:50:10+00
14051	4879	2	uncommon	\N	2026-02-18 22:50:10+00	2026-02-18 22:50:10+00
14052	4879	1	uncommon	\N	2026-02-18 22:50:10+00	2026-02-18 22:50:10+00
14053	4879	3	uncommon	\N	2026-02-18 22:50:10+00	2026-02-18 22:50:10+00
14054	4879	4	uncommon	\N	2026-02-18 22:50:10+00	2026-02-18 22:50:10+00
14055	4880	32	uncommon	\N	2026-02-18 22:50:10+00	2026-02-18 22:50:10+00
14056	4880	25	uncommon	\N	2026-02-18 22:50:10+00	2026-02-18 22:50:10+00
14057	4880	2	uncommon	\N	2026-02-18 22:50:10+00	2026-02-18 22:50:10+00
14058	4880	3	uncommon	\N	2026-02-18 22:50:10+00	2026-02-18 22:50:10+00
14059	4880	4	uncommon	\N	2026-02-18 22:50:10+00	2026-02-18 22:50:10+00
14060	4881	32	uncommon	\N	2026-02-18 22:50:10+00	2026-02-18 22:50:10+00
14061	4881	25	uncommon	\N	2026-02-18 22:50:10+00	2026-02-18 22:50:10+00
14062	4881	2	uncommon	\N	2026-02-18 22:50:10+00	2026-02-18 22:50:10+00
14063	4881	3	uncommon	\N	2026-02-18 22:50:10+00	2026-02-18 22:50:10+00
14064	4881	4	uncommon	\N	2026-02-18 22:50:10+00	2026-02-18 22:50:10+00
14065	4882	32	uncommon	\N	2026-02-18 22:50:10+00	2026-02-18 22:50:10+00
14066	4882	25	uncommon	\N	2026-02-18 22:50:10+00	2026-02-18 22:50:10+00
14067	4882	2	uncommon	\N	2026-02-18 22:50:10+00	2026-02-18 22:50:10+00
14068	4882	3	uncommon	\N	2026-02-18 22:50:10+00	2026-02-18 22:50:10+00
14069	4882	4	uncommon	\N	2026-02-18 22:50:10+00	2026-02-18 22:50:10+00
14070	4883	2	uncommon	\N	2026-02-18 22:50:44+00	2026-02-18 22:50:44+00
14071	4883	3	uncommon	\N	2026-02-18 22:50:44+00	2026-02-18 22:50:44+00
14072	4883	16	uncommon	\N	2026-02-18 22:50:44+00	2026-02-18 22:50:44+00
14073	4884	2	uncommon	\N	2026-02-18 22:50:44+00	2026-02-18 22:50:44+00
14074	4884	3	uncommon	\N	2026-02-18 22:50:44+00	2026-02-18 22:50:44+00
14075	4884	16	uncommon	\N	2026-02-18 22:50:44+00	2026-02-18 22:50:44+00
14076	4885	2	uncommon	\N	2026-02-18 22:50:44+00	2026-02-18 22:50:44+00
14077	4885	3	uncommon	\N	2026-02-18 22:50:44+00	2026-02-18 22:50:44+00
14078	4885	16	uncommon	\N	2026-02-18 22:50:44+00	2026-02-18 22:50:44+00
14079	4886	29	uncommon	\N	2026-02-18 22:51:11+00	2026-02-18 22:51:11+00
14080	4886	18	uncommon	\N	2026-02-18 22:51:11+00	2026-02-18 22:51:11+00
14081	4886	25	uncommon	\N	2026-02-18 22:51:11+00	2026-02-18 22:51:11+00
14082	4886	2	uncommon	\N	2026-02-18 22:51:11+00	2026-02-18 22:51:11+00
14083	4886	1	uncommon	\N	2026-02-18 22:51:11+00	2026-02-18 22:51:11+00
14084	4886	3	uncommon	\N	2026-02-18 22:51:11+00	2026-02-18 22:51:11+00
14085	4887	29	uncommon	\N	2026-02-18 22:51:11+00	2026-02-18 22:51:11+00
14086	4887	18	uncommon	\N	2026-02-18 22:51:11+00	2026-02-18 22:51:11+00
14087	4887	25	uncommon	\N	2026-02-18 22:51:11+00	2026-02-18 22:51:11+00
14088	4887	2	uncommon	\N	2026-02-18 22:51:11+00	2026-02-18 22:51:11+00
14089	4887	1	uncommon	\N	2026-02-18 22:51:11+00	2026-02-18 22:51:11+00
14090	4887	3	uncommon	\N	2026-02-18 22:51:11+00	2026-02-18 22:51:11+00
14091	4888	29	uncommon	\N	2026-02-18 22:51:11+00	2026-02-18 22:51:11+00
14092	4888	18	uncommon	\N	2026-02-18 22:51:11+00	2026-02-18 22:51:11+00
14093	4888	25	uncommon	\N	2026-02-18 22:51:11+00	2026-02-18 22:51:11+00
14094	4888	2	uncommon	\N	2026-02-18 22:51:11+00	2026-02-18 22:51:11+00
14095	4888	3	uncommon	\N	2026-02-18 22:51:11+00	2026-02-18 22:51:11+00
14096	4889	29	uncommon	\N	2026-02-18 22:51:11+00	2026-02-18 22:51:11+00
14097	4889	18	uncommon	\N	2026-02-18 22:51:11+00	2026-02-18 22:51:11+00
14098	4889	25	uncommon	\N	2026-02-18 22:51:11+00	2026-02-18 22:51:11+00
14099	4889	2	uncommon	\N	2026-02-18 22:51:11+00	2026-02-18 22:51:11+00
14100	4889	3	uncommon	\N	2026-02-18 22:51:11+00	2026-02-18 22:51:11+00
14101	4890	29	uncommon	\N	2026-02-18 22:51:11+00	2026-02-18 22:51:11+00
14102	4890	18	uncommon	\N	2026-02-18 22:51:11+00	2026-02-18 22:51:11+00
14103	4890	25	uncommon	\N	2026-02-18 22:51:11+00	2026-02-18 22:51:11+00
14104	4890	2	uncommon	\N	2026-02-18 22:51:11+00	2026-02-18 22:51:11+00
14105	4890	3	uncommon	\N	2026-02-18 22:51:11+00	2026-02-18 22:51:11+00
14106	4891	23	uncommon	\N	2026-02-18 22:51:39+00	2026-02-18 22:51:39+00
14107	4891	1	uncommon	\N	2026-02-18 22:51:39+00	2026-02-18 22:51:39+00
14108	4892	23	uncommon	\N	2026-02-18 22:51:39+00	2026-02-18 22:51:39+00
14109	4892	1	uncommon	\N	2026-02-18 22:51:39+00	2026-02-18 22:51:39+00
14110	4893	23	uncommon	\N	2026-02-18 22:51:39+00	2026-02-18 22:51:39+00
14111	4893	1	uncommon	\N	2026-02-18 22:51:39+00	2026-02-18 22:51:39+00
14112	4894	17	uncommon	\N	2026-02-18 22:52:05+00	2026-02-18 22:52:05+00
14113	4894	18	uncommon	\N	2026-02-18 22:52:05+00	2026-02-18 22:52:05+00
14114	4894	3	uncommon	\N	2026-02-18 22:52:05+00	2026-02-18 22:52:05+00
14115	4894	16	uncommon	\N	2026-02-18 22:52:05+00	2026-02-18 22:52:05+00
14116	4895	17	uncommon	\N	2026-02-18 22:52:05+00	2026-02-18 22:52:05+00
14117	4895	18	uncommon	\N	2026-02-18 22:52:05+00	2026-02-18 22:52:05+00
14118	4895	3	uncommon	\N	2026-02-18 22:52:05+00	2026-02-18 22:52:05+00
14119	4895	16	uncommon	\N	2026-02-18 22:52:05+00	2026-02-18 22:52:05+00
14120	4896	17	uncommon	\N	2026-02-18 22:52:05+00	2026-02-18 22:52:05+00
14121	4896	18	uncommon	\N	2026-02-18 22:52:05+00	2026-02-18 22:52:05+00
14122	4896	3	uncommon	\N	2026-02-18 22:52:05+00	2026-02-18 22:52:05+00
14123	4896	16	uncommon	\N	2026-02-18 22:52:05+00	2026-02-18 22:52:05+00
14124	4897	25	uncommon	\N	2026-02-18 22:52:42+00	2026-02-18 22:52:42+00
14125	4897	2	uncommon	\N	2026-02-18 22:52:42+00	2026-02-18 22:52:42+00
14126	4897	1	uncommon	\N	2026-02-18 22:52:42+00	2026-02-18 22:52:42+00
14127	4897	4	uncommon	\N	2026-02-18 22:52:42+00	2026-02-18 22:52:42+00
14128	4897	37	uncommon	\N	2026-02-18 22:52:42+00	2026-02-18 22:52:42+00
14129	4898	25	uncommon	\N	2026-02-18 22:52:42+00	2026-02-18 22:52:42+00
14130	4898	2	uncommon	\N	2026-02-18 22:52:42+00	2026-02-18 22:52:42+00
14131	4898	1	uncommon	\N	2026-02-18 22:52:42+00	2026-02-18 22:52:42+00
14132	4898	4	uncommon	\N	2026-02-18 22:52:42+00	2026-02-18 22:52:42+00
14133	4898	37	uncommon	\N	2026-02-18 22:52:42+00	2026-02-18 22:52:42+00
14134	4899	25	uncommon	\N	2026-02-18 22:52:42+00	2026-02-18 22:52:42+00
14135	4899	2	uncommon	\N	2026-02-18 22:52:42+00	2026-02-18 22:52:42+00
14136	4899	1	uncommon	\N	2026-02-18 22:52:42+00	2026-02-18 22:52:42+00
14137	4899	4	uncommon	\N	2026-02-18 22:52:42+00	2026-02-18 22:52:42+00
14138	4899	37	uncommon	\N	2026-02-18 22:52:42+00	2026-02-18 22:52:42+00
14139	4900	25	uncommon	\N	2026-02-18 22:52:42+00	2026-02-18 22:52:42+00
14140	4900	2	uncommon	\N	2026-02-18 22:52:42+00	2026-02-18 22:52:42+00
14141	4900	4	uncommon	\N	2026-02-18 22:52:42+00	2026-02-18 22:52:42+00
14142	4900	37	uncommon	\N	2026-02-18 22:52:42+00	2026-02-18 22:52:42+00
14143	4901	25	uncommon	\N	2026-02-18 22:52:42+00	2026-02-18 22:52:42+00
14144	4901	2	uncommon	\N	2026-02-18 22:52:42+00	2026-02-18 22:52:42+00
14145	4901	4	uncommon	\N	2026-02-18 22:52:42+00	2026-02-18 22:52:42+00
14146	4901	37	uncommon	\N	2026-02-18 22:52:42+00	2026-02-18 22:52:42+00
14147	4902	25	uncommon	\N	2026-02-18 22:52:42+00	2026-02-18 22:52:42+00
14148	4902	2	uncommon	\N	2026-02-18 22:52:42+00	2026-02-18 22:52:42+00
14149	4902	4	uncommon	\N	2026-02-18 22:52:42+00	2026-02-18 22:52:42+00
14150	4902	37	uncommon	\N	2026-02-18 22:52:42+00	2026-02-18 22:52:42+00
14151	4903	46	uncommon	\N	2026-02-18 22:53:19+00	2026-02-18 22:53:19+00
14152	4903	47	uncommon	\N	2026-02-18 22:53:19+00	2026-02-18 22:53:19+00
14153	4904	46	uncommon	\N	2026-02-18 22:53:19+00	2026-02-18 22:53:19+00
14154	4904	47	uncommon	\N	2026-02-18 22:53:19+00	2026-02-18 22:53:19+00
14155	4905	1	uncommon	\N	2026-02-18 22:53:50+00	2026-02-18 22:53:50+00
14156	4905	3	uncommon	\N	2026-02-18 22:53:50+00	2026-02-18 22:53:50+00
14157	4905	4	uncommon	\N	2026-02-18 22:53:50+00	2026-02-18 22:53:50+00
14158	4906	1	uncommon	\N	2026-02-18 22:53:50+00	2026-02-18 22:53:50+00
14159	4906	3	uncommon	\N	2026-02-18 22:53:50+00	2026-02-18 22:53:50+00
14160	4906	4	uncommon	\N	2026-02-18 22:53:50+00	2026-02-18 22:53:50+00
14161	4907	3	uncommon	\N	2026-02-18 22:53:50+00	2026-02-18 22:53:50+00
14162	4907	4	uncommon	\N	2026-02-18 22:53:50+00	2026-02-18 22:53:50+00
14163	4908	3	uncommon	\N	2026-02-18 22:53:50+00	2026-02-18 22:53:50+00
14164	4908	4	uncommon	\N	2026-02-18 22:53:50+00	2026-02-18 22:53:50+00
14165	4909	2	uncommon	\N	2026-02-18 22:54:25+00	2026-02-18 22:54:25+00
14166	4909	3	uncommon	\N	2026-02-18 22:54:25+00	2026-02-18 22:54:25+00
14167	4909	16	uncommon	\N	2026-02-18 22:54:25+00	2026-02-18 22:54:25+00
14168	4910	2	uncommon	\N	2026-02-18 22:54:25+00	2026-02-18 22:54:25+00
14169	4910	3	uncommon	\N	2026-02-18 22:54:25+00	2026-02-18 22:54:25+00
14170	4910	16	uncommon	\N	2026-02-18 22:54:25+00	2026-02-18 22:54:25+00
14171	4911	2	uncommon	\N	2026-02-18 22:54:25+00	2026-02-18 22:54:25+00
14172	4911	3	uncommon	\N	2026-02-18 22:54:25+00	2026-02-18 22:54:25+00
14173	4911	16	uncommon	\N	2026-02-18 22:54:25+00	2026-02-18 22:54:25+00
14174	4912	2	uncommon	\N	2026-02-18 22:54:56+00	2026-02-18 22:54:56+00
14175	4912	1	uncommon	\N	2026-02-18 22:54:56+00	2026-02-18 22:54:56+00
14176	4912	3	uncommon	\N	2026-02-18 22:54:56+00	2026-02-18 22:54:56+00
14177	4912	28	uncommon	\N	2026-02-18 22:54:56+00	2026-02-18 22:54:56+00
14178	4912	4	uncommon	\N	2026-02-18 22:54:56+00	2026-02-18 22:54:56+00
14179	4913	2	uncommon	\N	2026-02-18 22:54:56+00	2026-02-18 22:54:56+00
14180	4913	1	uncommon	\N	2026-02-18 22:54:56+00	2026-02-18 22:54:56+00
14181	4913	3	uncommon	\N	2026-02-18 22:54:56+00	2026-02-18 22:54:56+00
14182	4913	28	uncommon	\N	2026-02-18 22:54:56+00	2026-02-18 22:54:56+00
14183	4913	4	uncommon	\N	2026-02-18 22:54:56+00	2026-02-18 22:54:56+00
14184	4914	2	uncommon	\N	2026-02-18 22:54:56+00	2026-02-18 22:54:56+00
14185	4914	1	uncommon	\N	2026-02-18 22:54:56+00	2026-02-18 22:54:56+00
14186	4914	3	uncommon	\N	2026-02-18 22:54:56+00	2026-02-18 22:54:56+00
14187	4914	28	uncommon	\N	2026-02-18 22:54:56+00	2026-02-18 22:54:56+00
14188	4914	4	uncommon	\N	2026-02-18 22:54:56+00	2026-02-18 22:54:56+00
14189	4915	2	uncommon	\N	2026-02-18 22:54:56+00	2026-02-18 22:54:56+00
14190	4915	1	uncommon	\N	2026-02-18 22:54:56+00	2026-02-18 22:54:56+00
14191	4915	3	uncommon	\N	2026-02-18 22:54:56+00	2026-02-18 22:54:56+00
14192	4915	28	uncommon	\N	2026-02-18 22:54:56+00	2026-02-18 22:54:56+00
14193	4915	4	uncommon	\N	2026-02-18 22:54:56+00	2026-02-18 22:54:56+00
14194	4916	2	uncommon	\N	2026-02-18 22:54:56+00	2026-02-18 22:54:56+00
14195	4916	1	uncommon	\N	2026-02-18 22:54:56+00	2026-02-18 22:54:56+00
14196	4916	3	uncommon	\N	2026-02-18 22:54:56+00	2026-02-18 22:54:56+00
14197	4916	28	uncommon	\N	2026-02-18 22:54:56+00	2026-02-18 22:54:56+00
14198	4916	4	uncommon	\N	2026-02-18 22:54:56+00	2026-02-18 22:54:56+00
14199	4917	2	uncommon	\N	2026-02-18 22:54:56+00	2026-02-18 22:54:56+00
14200	4917	1	uncommon	\N	2026-02-18 22:54:56+00	2026-02-18 22:54:56+00
14201	4917	3	uncommon	\N	2026-02-18 22:54:56+00	2026-02-18 22:54:56+00
14202	4917	28	uncommon	\N	2026-02-18 22:54:56+00	2026-02-18 22:54:56+00
14203	4917	4	uncommon	\N	2026-02-18 22:54:56+00	2026-02-18 22:54:56+00
14204	4918	23	uncommon	\N	2026-02-18 22:55:46+00	2026-02-18 22:55:46+00
14205	4918	2	uncommon	\N	2026-02-18 22:55:46+00	2026-02-18 22:55:46+00
14206	4918	1	uncommon	\N	2026-02-18 22:55:46+00	2026-02-18 22:55:46+00
14207	4918	4	uncommon	\N	2026-02-18 22:55:46+00	2026-02-18 22:55:46+00
14208	4919	23	uncommon	\N	2026-02-18 22:55:46+00	2026-02-18 22:55:46+00
14209	4919	2	uncommon	\N	2026-02-18 22:55:46+00	2026-02-18 22:55:46+00
14210	4919	1	uncommon	\N	2026-02-18 22:55:46+00	2026-02-18 22:55:46+00
14211	4919	4	uncommon	\N	2026-02-18 22:55:46+00	2026-02-18 22:55:46+00
14212	4920	29	uncommon	\N	2026-02-18 22:56:14+00	2026-02-18 22:56:14+00
14213	4920	18	uncommon	\N	2026-02-18 22:56:14+00	2026-02-18 22:56:14+00
14214	4920	27	uncommon	\N	2026-02-18 22:56:14+00	2026-02-18 22:56:14+00
14215	4920	32	uncommon	\N	2026-02-18 22:56:14+00	2026-02-18 22:56:14+00
14216	4920	25	uncommon	\N	2026-02-18 22:56:14+00	2026-02-18 22:56:14+00
14217	4920	2	uncommon	\N	2026-02-18 22:56:14+00	2026-02-18 22:56:14+00
14218	4920	1	uncommon	\N	2026-02-18 22:56:14+00	2026-02-18 22:56:14+00
14219	4920	3	uncommon	\N	2026-02-18 22:56:14+00	2026-02-18 22:56:14+00
14220	4920	28	uncommon	\N	2026-02-18 22:56:14+00	2026-02-18 22:56:14+00
14221	4920	4	uncommon	\N	2026-02-18 22:56:14+00	2026-02-18 22:56:14+00
14222	4921	29	uncommon	\N	2026-02-18 22:56:14+00	2026-02-18 22:56:14+00
14223	4921	18	uncommon	\N	2026-02-18 22:56:14+00	2026-02-18 22:56:14+00
14224	4921	27	uncommon	\N	2026-02-18 22:56:14+00	2026-02-18 22:56:14+00
14225	4921	32	uncommon	\N	2026-02-18 22:56:14+00	2026-02-18 22:56:14+00
14226	4921	25	uncommon	\N	2026-02-18 22:56:14+00	2026-02-18 22:56:14+00
14227	4921	2	uncommon	\N	2026-02-18 22:56:14+00	2026-02-18 22:56:14+00
14228	4921	1	uncommon	\N	2026-02-18 22:56:14+00	2026-02-18 22:56:14+00
14229	4921	3	uncommon	\N	2026-02-18 22:56:14+00	2026-02-18 22:56:14+00
14230	4921	28	uncommon	\N	2026-02-18 22:56:14+00	2026-02-18 22:56:14+00
14231	4921	4	uncommon	\N	2026-02-18 22:56:14+00	2026-02-18 22:56:14+00
14232	4922	29	uncommon	\N	2026-02-18 22:56:14+00	2026-02-18 22:56:14+00
14233	4922	18	uncommon	\N	2026-02-18 22:56:14+00	2026-02-18 22:56:14+00
14234	4922	27	uncommon	\N	2026-02-18 22:56:14+00	2026-02-18 22:56:14+00
14235	4922	32	uncommon	\N	2026-02-18 22:56:14+00	2026-02-18 22:56:14+00
14236	4922	25	uncommon	\N	2026-02-18 22:56:14+00	2026-02-18 22:56:14+00
14237	4922	2	uncommon	\N	2026-02-18 22:56:14+00	2026-02-18 22:56:14+00
14238	4922	1	uncommon	\N	2026-02-18 22:56:14+00	2026-02-18 22:56:14+00
14239	4922	3	uncommon	\N	2026-02-18 22:56:14+00	2026-02-18 22:56:14+00
14240	4922	28	uncommon	\N	2026-02-18 22:56:14+00	2026-02-18 22:56:14+00
14241	4922	4	uncommon	\N	2026-02-18 22:56:14+00	2026-02-18 22:56:14+00
14242	4923	29	uncommon	\N	2026-02-18 22:56:14+00	2026-02-18 22:56:14+00
14243	4923	18	uncommon	\N	2026-02-18 22:56:14+00	2026-02-18 22:56:14+00
14244	4923	27	uncommon	\N	2026-02-18 22:56:14+00	2026-02-18 22:56:14+00
14245	4923	32	uncommon	\N	2026-02-18 22:56:14+00	2026-02-18 22:56:14+00
14246	4923	25	uncommon	\N	2026-02-18 22:56:14+00	2026-02-18 22:56:14+00
14247	4923	2	uncommon	\N	2026-02-18 22:56:14+00	2026-02-18 22:56:14+00
14248	4923	3	uncommon	\N	2026-02-18 22:56:14+00	2026-02-18 22:56:14+00
14249	4923	28	uncommon	\N	2026-02-18 22:56:14+00	2026-02-18 22:56:14+00
14250	4923	4	uncommon	\N	2026-02-18 22:56:14+00	2026-02-18 22:56:14+00
14251	4924	29	uncommon	\N	2026-02-18 22:56:14+00	2026-02-18 22:56:14+00
14252	4924	18	uncommon	\N	2026-02-18 22:56:14+00	2026-02-18 22:56:14+00
14253	4924	27	uncommon	\N	2026-02-18 22:56:14+00	2026-02-18 22:56:14+00
14254	4924	32	uncommon	\N	2026-02-18 22:56:14+00	2026-02-18 22:56:14+00
14255	4924	25	uncommon	\N	2026-02-18 22:56:14+00	2026-02-18 22:56:14+00
14256	4924	2	uncommon	\N	2026-02-18 22:56:14+00	2026-02-18 22:56:14+00
14257	4924	3	uncommon	\N	2026-02-18 22:56:14+00	2026-02-18 22:56:14+00
14258	4924	28	uncommon	\N	2026-02-18 22:56:14+00	2026-02-18 22:56:14+00
14259	4924	4	uncommon	\N	2026-02-18 22:56:14+00	2026-02-18 22:56:14+00
14260	4925	29	uncommon	\N	2026-02-18 22:56:14+00	2026-02-18 22:56:14+00
14261	4925	18	uncommon	\N	2026-02-18 22:56:14+00	2026-02-18 22:56:14+00
14262	4925	27	uncommon	\N	2026-02-18 22:56:14+00	2026-02-18 22:56:14+00
14263	4925	32	uncommon	\N	2026-02-18 22:56:14+00	2026-02-18 22:56:14+00
14264	4925	25	uncommon	\N	2026-02-18 22:56:14+00	2026-02-18 22:56:14+00
14265	4925	2	uncommon	\N	2026-02-18 22:56:14+00	2026-02-18 22:56:14+00
14266	4925	1	uncommon	\N	2026-02-18 22:56:14+00	2026-02-18 22:56:14+00
14267	4925	3	uncommon	\N	2026-02-18 22:56:14+00	2026-02-18 22:56:14+00
14268	4925	28	uncommon	\N	2026-02-18 22:56:14+00	2026-02-18 22:56:14+00
14269	4925	4	uncommon	\N	2026-02-18 22:56:14+00	2026-02-18 22:56:14+00
\.


--
-- Data for Name: protocol_dosages; Type: TABLE DATA; Schema: public; Owner: -
--

COPY public.protocol_dosages (id, protocol_id, dosage_id, schedule_id, is_default, is_required, sort_order, notes, created_at, updated_at) FROM stdin;
1648	751	62	1	f	t	0	General connective tissue support.	2025-09-08 01:12:59+00	2025-09-08 01:12:59+00
1649	751	63	1	f	f	1	Moderate tissue regeneration.	2025-09-08 01:12:59+00	2025-09-08 01:12:59+00
1650	751	37	1	f	f	2	Deep regenerative or anti-aging research.	2025-09-08 01:12:59+00	2025-09-08 01:12:59+00
1651	751	37	9	f	f	3	Maximum recommended dose.	2025-09-08 01:12:59+00	2025-09-08 01:12:59+00
1794	796	76	1	f	t	0	Low and well tolerable dose intended for general prostate support. 	2025-09-08 19:58:33+00	2025-09-08 19:58:33+00
1795	796	20	9	f	f	1	Moderate dose intended for higher severity treatment. 	2025-09-08 19:58:33+00	2025-09-08 19:58:33+00
1804	800	102	1	f	t	0	Low dose best used for maintenance in healthy individuals and preventive use for aging joints or mild stiffness.	2025-09-08 20:01:53+00	2025-09-08 20:01:53+00
1805	800	77	9	f	f	1	Standard/Moderate dose commonly used for mild to moderate joint or spine issues, recovery support from minor injury, active lifestyle support or recurring joint pain.	2025-09-08 20:01:53+00	2025-09-08 20:01:53+00
1806	800	105	11	f	f	2	High dose recommended for surgery rehab, moderate to severe degenerative joint conditions like osteoporosis, advanced osteochondrosis, spinal degeneration. Can also be split into 10mg - 4 times a day if desired.	2025-09-08 20:01:53+00	2025-09-08 20:01:53+00
1827	807	102	1	f	t	0	Low, Prophylactic dose. Best used for mild testosterone support, maintaining reproductive health and early aging stages.	2025-09-08 20:06:11+00	2025-09-08 20:06:11+00
1828	807	114	1	f	f	1	Moderate, Therapeutic dose. Best used used for enhancing libido, supporting spermatogenesis, restoring testicular function.	2025-09-08 20:06:11+00	2025-09-08 20:06:11+00
1870	819	102	1	f	t	0	Low dose, best used for preventive care, mild vascular support.	2025-09-08 20:14:15+00	2025-09-08 20:14:15+00
1871	819	113	11	f	f	1	Moderate dose, best used for treatment of atherosclerosis and senile purpura or other moderate severity vascular conditions.	2025-09-08 20:14:15+00	2025-09-08 20:14:15+00
1872	819	116	11	f	f	2	High dose intended for intense treatment of severe conditions like advanced vascular degeneration, stroke rehab or coronary bypass recovery. However it is important to mention, it has displayed a profound lack of adverse effects and very high safety and tolerability, even in extreme scenarios of long-term and high dose usage.	2025-09-08 20:14:15+00	2025-09-08 20:14:15+00
1887	824	82	1	f	t	0	Low, Prophylactic dose. Best used for mild thyroid support and general metabolic maintenance in otherwise healthy individuals.	2025-09-09 16:03:09+00	2025-09-09 16:03:09+00
1888	824	77	9	f	f	1	Moderate, Therapeutic dose. Commonly used for addressing symptoms of hypothyroidism or hyperthyroidism and metabolic imbalance.	2025-09-09 16:03:09+00	2025-09-09 16:03:09+00
1889	824	105	11	f	f	2	Intense, High dose. Usually reserved for severe thyroid dysfunction or support in a demanding enviroment. Though it is important to note, St. Petersburg Institute of Bioregulation reported no side effects or contraindications with Thyreogen use, but interindividual variability for intolerance and allergic sensitivity its still possible.	2025-09-09 16:03:09+00	2025-09-09 16:03:09+00
1923	836	134	1	f	t	0	Low dose. Good for general eye fatigue, screen-related stress, early aging prevention.	2025-09-10 05:34:16+00	2025-09-10 05:34:16+00
1924	836	113	9	f	f	1	Moderate dose. Great as support for early cataracts, macular degeneration, glaucoma.	2025-09-10 05:34:16+00	2025-09-10 05:34:16+00
1925	836	105	11	f	f	2	High dose. Perfect for eye strain, post-surgery recovery support, age-related vision changes.	2025-09-10 05:34:16+00	2025-09-10 05:34:16+00
1926	836	111	11	f	f	3	Aggressive dosage. Usually reserved for severe vision decline, post-injury recovery.	2025-09-10 05:34:16+00	2025-09-10 05:34:16+00
1927	837	102	1	f	t	0	Low dose. Great for general vascular support, anti-aging maintenance, preventive circulatory regulation.	2025-09-11 16:35:35+00	2025-09-11 16:35:35+00
1928	837	77	9	f	f	1	Moderate dose. Usually used for support in mild vascular dysfunction, prevention of atherosclerosis progression, normalization of blood pressure.	2025-09-11 16:35:35+00	2025-09-11 16:35:35+00
1929	837	81	11	f	f	2	High dose. Usually reserved for stronger regenerative support in chronic vascular insufficiency, recovery post-cardiovascular stress or long-term circulatory decline.	2025-09-11 16:35:35+00	2025-09-11 16:35:35+00
1936	840	134	1	f	t	0	Low dose. Good for general respiratory support, seasonal prevention, mild post-infectious recovery.	2025-09-11 17:32:31+00	2025-09-11 17:32:31+00
1937	840	113	9	f	f	1	Moderate dose. Useful for chronic bronchitis, mild asthma, support during prolonged respiratory illness.	2025-09-11 17:32:31+00	2025-09-11 17:32:31+00
1938	840	105	11	f	f	2	High dose. Usually reserved for severe chronic bronchitis, COPD adjunct therapy, post-pneumonia lung recovery, age-related pulmonary decline.	2025-09-11 17:32:31+00	2025-09-11 17:32:31+00
1955	846	76	1	f	t	0	Low dose best used as an adjunct, testing response or for pediatric treatment.	2025-09-16 16:18:41+00	2025-09-16 16:18:41+00
1956	846	20	9	f	f	1	Standard dose usually used for Retinal or Optic Nerve damage.	2025-09-16 16:18:41+00	2025-09-16 16:18:41+00
1963	849	102	1	f	t	0	Lowest practical dose.\n	2025-09-17 01:36:50+00	2025-09-17 01:36:50+00
1964	849	77	9	f	f	1	Moderate dose. Most commonly used.\n	2025-09-17 01:36:50+00	2025-09-17 01:36:50+00
1965	849	31	11	f	f	2	High dose for aggressive results.	2025-09-17 01:36:50+00	2025-09-17 01:36:50+00
1966	850	102	1	f	t	0	Lowest practical dose.	2025-09-17 01:39:29+00	2025-09-17 01:39:29+00
1967	850	77	9	f	f	1	Moderate dose. Most commonly used.	2025-09-17 01:39:29+00	2025-09-17 01:39:29+00
1968	850	81	11	f	f	2	High dose for aggressive results.	2025-09-17 01:39:29+00	2025-09-17 01:39:29+00
1972	852	102	1	f	t	0	Lowest practical dose.	2025-09-20 23:37:48+00	2025-09-20 23:37:48+00
1973	852	77	9	f	f	1	Moderate dose. Most commonly used.	2025-09-20 23:37:48+00	2025-09-20 23:37:48+00
1974	852	31	11	f	f	2	High dose for aggressive results.	2025-09-20 23:37:48+00	2025-09-20 23:37:48+00
1975	852	105	9	f	f	3	Very high dose for intensive care.	2025-09-20 23:37:48+00	2025-09-20 23:37:48+00
1976	853	102	1	f	t	0	Lowest practical dose.\n	2025-09-20 23:44:02+00	2025-09-20 23:44:02+00
1977	853	77	9	f	f	1	Moderate dose. Most commonly used.\n	2025-09-20 23:44:02+00	2025-09-20 23:44:02+00
1978	853	81	11	f	f	2	High dose for aggressive results.	2025-09-20 23:44:02+00	2025-09-20 23:44:02+00
1979	854	102	1	f	t	0	Lowest practical dose.\n	2025-09-20 23:54:27+00	2025-09-20 23:54:27+00
1980	854	77	9	f	f	1	Moderate dose. Most commonly used.\n	2025-09-20 23:54:27+00	2025-09-20 23:54:27+00
1981	854	31	11	f	f	2	High dose for aggressive results.	2025-09-20 23:54:27+00	2025-09-20 23:54:27+00
1982	855	102	1	f	t	0	Lowest practical dose.\n	2025-09-21 00:01:52+00	2025-09-21 00:01:52+00
1983	855	77	9	f	f	1	Moderate dose. Most commonly used.\n	2025-09-21 00:01:52+00	2025-09-21 00:01:52+00
1984	855	81	11	f	f	2	High dose for aggressive results.	2025-09-21 00:01:52+00	2025-09-21 00:01:52+00
1985	856	102	1	f	t	0	Lowest practical dose.\n	2025-09-21 00:10:12+00	2025-09-21 00:10:12+00
1986	856	77	9	f	f	1	Moderate dose. Most commonly used.\n	2025-09-21 00:10:12+00	2025-09-21 00:10:12+00
1987	856	81	11	f	f	2	High dose for aggressive results.	2025-09-21 00:10:12+00	2025-09-21 00:10:12+00
2319	974	99	1	f	t	0	Starting dose for receptor binding inhibition in rodents; extrapolated to humans	2025-09-29 07:34:42+00	2025-09-29 07:34:42+00
2320	974	100	1	f	f	1	Middle range used in stress-response modulation studies	2025-09-29 07:34:42+00	2025-09-29 07:34:42+00
2321	974	101	8	f	f	2	Higher doses for prolonged CRF receptor blockade or chronic stress models	2025-09-29 07:34:42+00	2025-09-29 07:34:42+00
2322	975	99	1	f	t	0	Microdosing or acute CNS receptor targeting	2025-09-29 07:34:42+00	2025-09-29 07:34:42+00
2323	975	63	1	f	f	1	Common experimental range for peptides crossing blood-brain barrier intranasally	2025-09-29 07:34:42+00	2025-09-29 07:34:42+00
2324	975	37	1	f	f	2	Maximum experimental range for peptides crossing blood-brain barrier intranasally	2025-09-29 07:34:42+00	2025-09-29 07:34:42+00
2325	975	37	9	f	f	3	Maximum experimental range for peptides crossing blood-brain barrier intranasally	2025-09-29 07:34:42+00	2025-09-29 07:34:42+00
2490	1034	62	1	f	t	0	Low dosage to test response.	2025-10-05 11:14:53+00	2025-10-05 11:14:53+00
2491	1034	139	1	f	f	1	Titrate up if tolerable.	2025-10-05 11:14:53+00	2025-10-05 11:14:53+00
2492	1034	101	9	f	f	2	Clinical trials dosage. Splitting to twice daily recommended, due to very short half life.	2025-10-05 11:14:53+00	2025-10-05 11:14:53+00
2493	1034	90	9	f	f	3	Maximum recommended dosage. Splitting to twice daily recommended, due to very short half life.	2025-10-05 11:14:53+00	2025-10-05 11:14:53+00
2502	1043	142	9	f	t	0	Clinical concentration. 	2025-10-07 12:13:00+00	2025-10-07 12:13:00+00
2503	1043	143	9	f	f	1	Experimental concentration. Lacks clinical data but due to its seemingly non-existant side-effect profile should be safe	2025-10-07 12:13:00+00	2025-10-07 12:13:00+00
2816	1151	59	12	f	t	0	Low dose. Ideally for titration to higher dose.	2025-11-02 04:16:00+00	2025-11-02 04:16:00+00
2817	1151	60	12	f	f	1	Medium dose. Titrate from 0.25mg.	2025-11-02 04:16:00+00	2025-11-02 04:16:00+00
2818	1151	55	12	f	f	2	High dose. Titrate from 0.25 mg to 0.5mg and then to 1mg.	2025-11-02 04:16:00+00	2025-11-02 04:16:00+00
2819	1151	40	12	f	f	3	Maximum recommended dose.	2025-11-02 04:16:00+00	2025-11-02 04:16:00+00
2910	1180	125	1	f	t	0	Low dosage. Dosage and frequency increases risk of tolerance.	2025-11-04 18:59:11+00	2025-11-04 18:59:11+00
2911	1180	126	1	f	f	1	Moderate and most commonly used dosage. Dosage and frequency increases risk of tolerance.	2025-11-04 18:59:11+00	2025-11-04 18:59:11+00
2912	1180	127	1	f	f	2	High dosage. Highly tolerance forming and possibility of headaches is high.	2025-11-04 18:59:11+00	2025-11-04 18:59:11+00
2951	1194	51	1	f	t	0	Low dose. Test response especially blood pressure before increasing.	2025-11-05 05:45:16+00	2025-11-05 05:45:16+00
2952	1194	113	1	f	f	1	Moderate dose. Common mainstay.	2025-11-05 05:45:16+00	2025-11-05 05:45:16+00
2953	1194	116	1	f	f	2	Maximum recommended dose.	2025-11-05 05:45:16+00	2025-11-05 05:45:16+00
2997	1205	180	11	f	t	0	Low dose. Usually utilized as a starting dose or when lacking indications or for recreational cognitive enhancement. Length of use increases efficacy. Increase dose every 4 days if needed.	2025-11-06 21:39:17+00	2025-11-06 21:39:17+00
2998	1205	181	11	f	f	1	Increased dose. More significant effects. Length of use increases efficacy. Increase dose every 4 days if needed.	2025-11-06 21:39:17+00	2025-11-06 21:39:17+00
2999	1205	185	11	f	f	2	Moderate dose. Effects are quite noticeable at this dosage range. Length of use increases efficacy. Increase dose every 4 days if needed.	2025-11-06 21:39:17+00	2025-11-06 21:39:17+00
3000	1205	186	11	f	f	3	High dose. Used for clinical indications. Length of use increases efficacy. Increase dose every 4 days if needed.	2025-11-06 21:39:17+00	2025-11-06 21:39:17+00
3001	1205	187	11	f	f	4	Maximum recommended dose.	2025-11-06 21:39:17+00	2025-11-06 21:39:17+00
3016	1211	128	13	f	t	0	Low dose. Mild effect.	2025-11-07 03:35:52+00	2025-11-07 03:35:52+00
3017	1211	152	13	f	f	1	Optimal dose for performance enhancement	2025-11-07 03:35:52+00	2025-11-07 03:35:52+00
3018	1211	193	1	f	f	2	High dose. Reserved for cancer and dementia usage due to lack of efficacy over thrice weekly for performance enhancement.	2025-11-07 03:35:52+00	2025-11-07 03:35:52+00
3040	1221	141	1	f	t	0	Use enough to cover area. Ideally used after microneedling and potentially combining with oral Valproic acid.	2025-11-14 07:52:37+00	2025-11-14 07:52:37+00
3041	1222	20	1	f	t	0	10 scalp injections divided across the problematic areas. Unfortunately data about injection is sparse so use with care.	2025-11-14 07:52:37+00	2025-11-14 07:52:37+00
3060	1230	166	1	f	t	0	Low dose. Least habit-forming and therapeutic dose. Frequency increases risk of dependence.	2025-11-16 02:49:22+00	2025-11-16 02:49:22+00
3061	1230	167	1	f	f	1	Most commonly used dose. High end of therapeutic and low end of recreational dosages. Frequency increases risk of dependence.	2025-11-16 02:49:22+00	2025-11-16 02:49:22+00
3062	1230	168	1	f	f	2	High dose. Heavily stepping into recreational or severe social anxiety dosage range. Frequency increases risk of dependence.	2025-11-16 02:49:22+00	2025-11-16 02:49:22+00
3063	1230	169	1	f	f	3	Maximum recommended dose. Highly recreational dosage range. Frequency increases risk of dependence.	2025-11-16 02:49:22+00	2025-11-16 02:49:22+00
3116	1247	76	14	f	t	0	Low dosage. Safe without significant behavioral discipline during use.	2025-11-18 04:03:47+00	2025-11-18 04:03:47+00
3117	1247	77	14	f	f	1	Moderate dosage. Disciplined behavior for beneficial habit forming is recommended.	2025-11-18 04:03:47+00	2025-11-18 04:03:47+00
3118	1247	105	14	f	f	2	High dosage. Disciplined behavior for beneficial habit forming is highly recommended.	2025-11-18 04:03:47+00	2025-11-18 04:03:47+00
3119	1248	38	15	f	t	0	Low dosage up to thrice daily. Safe without significant behavioral discipline during use.	2025-11-18 04:03:47+00	2025-11-18 04:03:47+00
3120	1248	39	15	f	f	1	Standard dosage up to thrice daily. Disciplined behavior for beneficial habit forming is recommended.	2025-11-18 04:03:47+00	2025-11-18 04:03:47+00
3181	1271	148	1	f	t	0	Low dose subcutaneous injection.	2025-11-18 11:08:14+00	2025-11-18 11:08:14+00
3182	1271	152	1	f	f	1	Standard dose subcutaneous injection.	2025-11-18 11:08:14+00	2025-11-18 11:08:14+00
3183	1272	175	1	f	t	0	Minimal oral dose. Good for testing response but otherwise ineffective.	2025-11-18 11:08:14+00	2025-11-18 11:08:14+00
3184	1272	167	1	f	f	1	Low end moderate dose. Light effect is present.	2025-11-18 11:08:14+00	2025-11-18 11:08:14+00
3185	1272	207	1	f	f	2	High end moderate dose. Effective and well tested.	2025-11-18 11:08:14+00	2025-11-18 11:08:14+00
3186	1272	208	1	f	f	3	High dose. Not well tested clinically, but anecdotally most efficacious due to low bioavailability.	2025-11-18 11:08:14+00	2025-11-18 11:08:14+00
3257	1295	102	1	f	t	0	Low dose. Usually used to test response or for light effects.	2025-11-29 11:36:41+00	2025-11-29 11:36:41+00
3258	1295	113	1	f	f	1	Medium dose. Most commonly used with plenty of experience reports.	2025-11-29 11:36:41+00	2025-11-29 11:36:41+00
3259	1295	158	1	f	f	2	Maximum dosage. Intense effects so should be used carefully.	2025-11-29 11:36:41+00	2025-11-29 11:36:41+00
3270	1299	76	1	f	t	0	Low dose. Effective and well documented.	2025-11-29 12:10:25+00	2025-11-29 12:10:25+00
3271	1299	77	1	f	f	1	Higher dose. Anything above 5mg daily is experimental.	2025-11-29 12:10:25+00	2025-11-29 12:10:25+00
3272	1299	105	1	f	f	2	High Dose. Usually used for on-demand use, but experimentally can be used daily, however this approach necessitates titration otherwise side effects are dangerous.	2025-11-29 12:10:25+00	2025-11-29 12:10:25+00
3317	1313	194	1	f	t	0	Low dose. More budget friendly while achieving majority of the effect.	2025-11-29 14:58:57+00	2025-11-29 14:58:57+00
3318	1313	195	1	f	f	1	Medium dosage. Sweet middle if a slight increase in efficacy is desired.	2025-11-29 14:58:57+00	2025-11-29 14:58:57+00
3319	1313	196	1	f	f	2	High dose. Maximum efficacy.	2025-11-29 14:58:57+00	2025-11-29 14:58:57+00
3320	1314	198	1	f	t	0	Standard recommended dose. Taken 1-3h before sexual intercouse. Maximum once daily.	2025-11-29 15:01:51+00	2025-11-29 15:01:51+00
3321	1314	199	1	f	f	1	High dose if lower dose is ineffective.  Taken 1-3h before sexual intercouse. Maximum once daily.	2025-11-29 15:01:51+00	2025-11-29 15:01:51+00
3336	1319	102	9	f	t	0	A prophylactic maintenance dose.	2025-11-29 15:19:19+00	2025-11-29 15:19:19+00
3337	1319	113	11	f	f	1	Most often used for menopause support and general neuroendocrine support.	2025-11-29 15:19:19+00	2025-11-29 15:19:19+00
3338	1319	105	11	f	f	2	Ideal for post-chemo and radiation.	2025-11-29 15:19:19+00	2025-11-29 15:19:19+00
3392	1335	117	1	f	t	0	Low dose. Intended use is to evaluate efficacy and tolerance.	2025-12-04 17:40:00+00	2025-12-04 17:40:00+00
3393	1335	49	14	f	f	1	Dose used in burn trauma and sepsis models - effectively modulates neuroimmune and metabolic stress responses.	2025-12-04 17:40:00+00	2025-12-04 17:40:00+00
3394	1335	119	14	f	f	2	ANIMAL DOSAGE: Maximum dose tested in safety studies with no organ toxicity or visible pathology compared to controls observed, indicating high tolerability.	2025-12-04 17:40:00+00	2025-12-04 17:40:00+00
3432	1346	136	1	f	t	0	Low dose. Good for preventive immune support, maintenance during mild stress or seasonal infection risk.	2025-12-04 18:47:23+00	2025-12-04 18:47:23+00
3433	1346	138	1	f	f	1	Moderate dose. Good for treatment of acute respiratory infections, recovery post-illness, or support during mild immunodeficiency.	2025-12-04 18:47:23+00	2025-12-04 18:47:23+00
3434	1346	47	9	f	f	2	High dose. Usually reserved for treatment of acute respiratory infections, recovery post-illness, or support during mild immunodeficiency.	2025-12-04 18:47:23+00	2025-12-04 18:47:23+00
3435	1346	101	9	f	f	3	Maximum recommended dose. Usually reserved for treatment of acute respiratory infections, recovery post-illness, or support during mild immunodeficiency.	2025-12-04 18:47:23+00	2025-12-04 18:47:23+00
3618	1404	235	1	f	t	0	Low dose, useful to assess response but is usually not enough.	2025-12-14 17:51:31+00	2025-12-14 17:51:31+00
3619	1404	236	1	f	f	1	Standard dose used by majority of people.	2025-12-14 17:51:31+00	2025-12-14 17:51:31+00
3620	1404	237	1	f	f	2	Maximum recommended dose used clinically.	2025-12-14 17:51:31+00	2025-12-14 17:51:31+00
3663	1415	248	1	f	t	0	Standard dosage for bodyweight 60-90kg	2025-12-18 20:41:49+00	2025-12-18 20:41:49+00
3664	1415	249	1	f	f	1	Maximum dosage for atleast 90kg bodyweight.	2025-12-18 20:41:49+00	2025-12-18 20:41:49+00
3671	1419	128	1	f	t	0	Standard starting dose. Significant health benefits and high tolerance.	2025-12-18 23:39:55+00	2025-12-18 23:39:55+00
3672	1419	251	1	f	f	1	Moderate dose. Can be used if 100mg is well tolerated. Increased risk of side effects, but efficacy is enhanced.	2025-12-18 23:39:55+00	2025-12-18 23:39:55+00
3673	1419	252	1	f	f	2	High dose. Can be used if 200mg is well tolerated. Significantly increased risk of side effects, but efficacy is very strongly enhanced.	2025-12-18 23:39:55+00	2025-12-18 23:39:55+00
3676	1421	51	1	f	t	0	Standard starting dose. Is sufficient in most cases.	2025-12-19 00:17:45+00	2025-12-19 00:17:45+00
3677	1421	237	1	f	f	1	Enhanced dose. Can be used for severe cases.	2025-12-19 00:17:45+00	2025-12-19 00:17:45+00
3696	1425	253	12	f	t	0	Starting dose. If tolerated well can proceed to titrate up after 4 weeks.	2025-12-19 23:23:05+00	2025-12-19 23:23:05+00
3697	1425	254	12	f	f	1	Titration dose. If tolerated well can proceed to titrate up after 4 weeks.	2025-12-19 23:23:05+00	2025-12-19 23:23:05+00
3698	1425	255	12	f	f	2	Titration dose. If tolerated well can proceed to titrate up after 4 weeks.	2025-12-19 23:23:05+00	2025-12-19 23:23:05+00
3699	1425	256	12	f	f	3	Titration dose. If tolerated well can proceed to titrate up after 4 weeks.	2025-12-19 23:23:05+00	2025-12-19 23:23:05+00
3700	1425	257	12	f	f	4	Titration dose. If tolerated well can proceed to titrate up after 4 weeks.	2025-12-19 23:23:05+00	2025-12-19 23:23:05+00
3701	1425	258	12	f	f	5	Maximum dosage. No further titration is recommendable.	2025-12-19 23:23:05+00	2025-12-19 23:23:05+00
3706	1428	134	9	f	t	0	Starting dosage. Is often also sufficient as is.	2025-12-19 23:59:41+00	2025-12-19 23:59:41+00
3707	1428	259	9	f	f	1	Medium dosage. Most commonly used dose.	2025-12-19 23:59:41+00	2025-12-19 23:59:41+00
3708	1428	53	9	f	f	2	Maximum clinical dosage.	2025-12-19 23:59:41+00	2025-12-19 23:59:41+00
3715	1431	22	11	f	t	0	\N	2025-12-21 01:02:09+00	2025-12-21 01:02:09+00
3716	1431	91	11	f	f	1	\N	2025-12-21 01:02:09+00	2025-12-21 01:02:09+00
3717	1431	40	11	f	f	2	\N	2025-12-21 01:02:09+00	2025-12-21 01:02:09+00
4169	1567	134	11	f	t	0	Low dose.	2026-01-16 23:34:16+00	2026-01-16 23:34:16+00
4170	1567	173	11	f	f	1	Moderate dose.	2026-01-16 23:34:16+00	2026-01-16 23:34:16+00
4171	1567	174	11	f	f	2	Maximum dose.	2026-01-16 23:34:16+00	2026-01-16 23:34:16+00
4243	1586	197	1	f	t	0	Standard dose that showed clinical efficacy.	2026-01-24 04:39:42+00	2026-01-24 04:39:42+00
4324	1611	166	1	f	t	0	Low dose. Least habit-forming and therapeutic dose. Frequency increases risk of dependence.	2026-02-05 19:30:37+00	2026-02-05 19:30:37+00
4325	1611	167	1	f	f	1	Most commonly used dose. High end of therapeutic and low end of recreational dosages. Frequency increases risk of dependence.	2026-02-05 19:30:37+00	2026-02-05 19:30:37+00
4326	1611	168	1	f	f	2	High dose. Heavily stepping into recreational or severe social anxiety dosage range. Frequency increases risk of dependence.	2026-02-05 19:30:37+00	2026-02-05 19:30:37+00
4327	1611	169	1	f	f	3	Maximum recommended dose. Highly recreational dosage range. Frequency increases risk of dependence.	2026-02-05 19:30:37+00	2026-02-05 19:30:37+00
4365	1623	38	12	f	t	0	Low dose to test the response.	2026-02-06 00:22:09+00	2026-02-06 00:22:09+00
4366	1623	39	12	f	f	1	Titrate up.	2026-02-06 00:22:09+00	2026-02-06 00:22:09+00
4367	1623	61	12	f	f	2	Maximum weekly dose.	2026-02-06 00:22:09+00	2026-02-06 00:22:09+00
4368	1624	22	1	f	t	0	Low dose.	2026-02-06 00:22:55+00	2026-02-06 00:22:55+00
4369	1624	64	1	f	f	1	Moderate dose. Preferred by most.	2026-02-06 00:22:55+00	2026-02-06 00:22:55+00
4370	1625	102	1	f	t	0	Low, effective and sustainable dose.	2026-02-06 00:23:53+00	2026-02-06 00:23:53+00
4371	1625	103	1	f	f	1	Medium dose. Still sustainable with higher efficacy.	2026-02-06 00:23:53+00	2026-02-06 00:23:53+00
4372	1625	104	1	f	f	2	High dose.	2026-02-06 00:23:53+00	2026-02-06 00:23:53+00
4373	1625	53	1	f	f	3	Maximum recommended dose.	2026-02-06 00:23:53+00	2026-02-06 00:23:53+00
4374	1626	102	11	f	t	0	Low, effective and sustainable dose.	2026-02-06 00:23:53+00	2026-02-06 00:23:53+00
4375	1626	103	11	f	f	1	Medium dose. Still sustainable with higher efficacy.	2026-02-06 00:23:53+00	2026-02-06 00:23:53+00
4376	1626	104	11	f	f	2	Maximum recommended dose.	2026-02-06 00:23:53+00	2026-02-06 00:23:53+00
4381	1628	35	1	f	t	0	Safe and  Cost effective.	2026-02-06 00:24:33+00	2026-02-06 00:24:33+00
4382	1628	42	1	f	f	1	Safe bet for moderate to severe SFN, diabetic neuropathy, autoimmune flare regulation, inflammation resolution.	2026-02-06 00:24:33+00	2026-02-06 00:24:33+00
4383	1628	93	9	f	f	2	Theoretical Maximum Efficacy protocol.	2026-02-06 00:24:33+00	2026-02-06 00:24:33+00
4384	1629	38	9	f	t	0	500mg per spray. 4 sprays a day. Safe and cost effective protocol.	2026-02-06 00:24:33+00	2026-02-06 00:24:33+00
4385	1629	39	9	f	f	1	1mg per spray. 4 sprays a day. Optimal Protocol.\n\n\n	2026-02-06 00:24:33+00	2026-02-06 00:24:33+00
4386	1629	23	9	f	f	2	2mg per spray. 4 sprays a day. The most effective protocol.	2026-02-06 00:24:33+00	2026-02-06 00:24:33+00
4387	1630	62	9	f	t	0	Low dosage. Preferred by most users. Preferred dose for slow, accumulative treatment.	2026-02-06 00:24:51+00	2026-02-06 00:24:51+00
4388	1630	63	9	f	f	1	Moderate to high dosage. Dose-linear escalation of systemic collagen degradation so use with care.	2026-02-06 00:24:51+00	2026-02-06 00:24:51+00
4389	1630	112	9	f	f	2	Maximum recommendable dosage. Arthralgia very likely in which case coming off is highly recommended.	2026-02-06 00:24:51+00	2026-02-06 00:24:51+00
4400	1634	38	1	f	t	0	Low, Prophylactic dose. Perfect for preventive care, smoking-related risk, seasonal lung stress.	2026-02-06 00:26:49+00	2026-02-06 00:26:49+00
4401	1634	39	1	f	f	1	Moderate therapeutic dose, best used for enhancing standard therapy efficacy in bronchitis, asthma, COPD.	2026-02-06 00:26:49+00	2026-02-06 00:26:49+00
4402	1634	40	1	f	f	2	High end dose, usually reserved for when intensive treatment is needed. Best used for acute respiratory recovery or severe asthma/COPD flare.	2026-02-06 00:26:49+00	2026-02-06 00:26:49+00
4403	1635	102	1	f	t	0	Low, Prophylactic dose. Perfect for preventive care, smoking-related risk, seasonal lung stress.	2026-02-06 00:26:49+00	2026-02-06 00:26:49+00
4404	1635	113	1	f	f	1	Moderate therapeutic dose, best used for enhancing standard therapy efficacy in bronchitis, asthma, COPD.	2026-02-06 00:26:49+00	2026-02-06 00:26:49+00
4405	1635	105	9	f	f	2	High end dose, usually reserved for when intensive treatment is needed. Best used for acute respiratory recovery or severe asthma/COPD flare.	2026-02-06 00:26:49+00	2026-02-06 00:26:49+00
4406	1636	241	12	f	t	0	\N	2026-02-06 00:27:10+00	2026-02-06 00:27:10+00
4407	1636	242	12	f	f	1	\N	2026-02-06 00:27:10+00	2026-02-06 00:27:10+00
4408	1636	243	12	f	f	2	\N	2026-02-06 00:27:10+00	2026-02-06 00:27:10+00
4409	1636	244	12	f	f	3	\N	2026-02-06 00:27:10+00	2026-02-06 00:27:10+00
4410	1636	245	12	f	f	4	\N	2026-02-06 00:27:10+00	2026-02-06 00:27:10+00
4411	1636	246	12	f	f	5	\N	2026-02-06 00:27:10+00	2026-02-06 00:27:10+00
4412	1636	247	12	f	f	6	\N	2026-02-06 00:27:10+00	2026-02-06 00:27:10+00
4413	1637	229	9	f	t	0	Low concentration for conservative usage.	2026-02-06 00:27:33+00	2026-02-06 00:27:33+00
4414	1637	230	9	f	f	1	Standard and significantly efficacious concentration.	2026-02-06 00:27:33+00	2026-02-06 00:27:33+00
4415	1638	162	1	f	t	0	Intramuscular injection of up to 5ml for standard usage. 1ml consists of 215.2mg Cerebroprotein Hydrolysate.	2026-02-06 00:27:51+00	2026-02-06 00:27:51+00
4416	1638	163	1	f	f	1	IV drip of up to 10ml for standard usage. 1ml consists of 215.2mg Cerebroprotein Hydrolysate.	2026-02-06 00:27:51+00	2026-02-06 00:27:51+00
4417	1638	164	1	f	f	2	Starting dose of IV drip for clinical cognitive decline or brain injury therapy. 1ml consists of 215.2mg Cerebroprotein Hydrolysate.	2026-02-06 00:27:51+00	2026-02-06 00:27:51+00
4418	1638	165	1	f	f	3	Maximum clinical dose for cognitive decline. 1ml consists of 215.2mg Cerebroprotein Hydrolysate.	2026-02-06 00:27:51+00	2026-02-06 00:27:51+00
4419	1639	102	1	f	t	0	Low, Prophylactic dose. Best used for mild issues like chronic dry cough or gut support.	2026-02-06 00:28:06+00	2026-02-06 00:28:06+00
4420	1639	77	9	f	f	1	Moderate, Therapeutic dose. Commonly used for Chronic bronchitis and asthma, gastritis or athletic recovery.	2026-02-06 00:28:06+00	2026-02-06 00:28:06+00
4421	1639	105	9	f	f	2	Intensive, Therapeutic dose. Usually used for pulmonary fibrosis, mucosal healing and supporting intense endurance protocols.	2026-02-06 00:28:06+00	2026-02-06 00:28:06+00
4422	1640	35	1	f	t	0	Low, Prophylactic dose. Best used for mild issues like chronic dry cough or gut support.	2026-02-06 00:28:06+00	2026-02-06 00:28:06+00
4423	1640	77	1	f	f	1	Moderate, Therapeutic dose. Commonly used for Chronic bronchitis and asthma, gastritis or athletic recovery.	2026-02-06 00:28:06+00	2026-02-06 00:28:06+00
4424	1640	105	1	f	f	2	Intensive, Therapeutic dose. Usually used for pulmonary fibrosis, mucosal healing and supporting intense endurance protocols.	2026-02-06 00:28:06+00	2026-02-06 00:28:06+00
4435	1644	102	14	f	t	0	Ideal dose for prophylactic therapy or for enhancing immune resilience in otherwise healthy individuals.	2026-02-06 00:31:07+00	2026-02-06 00:31:07+00
4436	1644	77	9	f	f	1	Most common dose - used for moderate infections and moderate immune suppresion.	2026-02-06 00:31:07+00	2026-02-06 00:31:07+00
4437	1644	81	11	f	f	2	High dose reserved for severe immunocompromise, chemotherapy rehab, radiation exposure, aging-related immune decline or severe infections.	2026-02-06 00:31:07+00	2026-02-06 00:31:07+00
4438	1645	22	13	f	t	0	Ideal dose for prophylactic therapy or for enhancing immune resilience in otherwise healthy individuals.	2026-02-06 00:31:07+00	2026-02-06 00:31:07+00
4439	1645	115	13	f	f	1	Most common dose - used for moderate infections and moderate immune suppresion.	2026-02-06 00:31:07+00	2026-02-06 00:31:07+00
4440	1645	65	13	f	f	2	High dose reserved for severe immunocompromise, chemotherapy rehab, radiation exposure, aging-related immune decline or severe infections.	2026-02-06 00:31:07+00	2026-02-06 00:31:07+00
4449	1648	38	1	f	t	0	Low sustainable dose.	2026-02-06 00:31:49+00	2026-02-06 00:31:49+00
4450	1648	227	1	f	f	1	Moderate dose with significant efficacy.	2026-02-06 00:31:49+00	2026-02-06 00:31:49+00
4451	1648	40	1	f	f	2	Maximum recommended dose. High likelihood of adverse effects.	2026-02-06 00:31:49+00	2026-02-06 00:31:49+00
4458	1651	35	1	f	t	0	Low dose. Preventive / maintenance purposes.	2026-02-06 00:32:45+00	2026-02-06 00:32:45+00
4459	1651	30	1	f	f	1	Medium dose. Anti-aging and cellular rejuvenation purposes.	2026-02-06 00:32:45+00	2026-02-06 00:32:45+00
4460	1651	81	1	f	f	2	Therapeutic, telomere restoration, severe age-related decline	2026-02-06 00:32:45+00	2026-02-06 00:32:45+00
4461	1652	62	9	f	t	0	Low dose. Preventive / maintenance purposes.	2026-02-06 00:32:45+00	2026-02-06 00:32:45+00
4462	1652	63	9	f	f	1	Medium dose. Cognitive support, circadian regulation. 	2026-02-06 00:32:45+00	2026-02-06 00:32:45+00
4463	1652	55	9	f	f	2	High dose. Therapeutic or neurodegenerative protocols	2026-02-06 00:32:45+00	2026-02-06 00:32:45+00
4464	1652	55	11	f	f	3	High-end of high dosage. Therapeutic or neurodegenerative protocols.	2026-02-06 00:32:45+00	2026-02-06 00:32:45+00
4465	1653	106	11	f	t	0	Low concentration. General anti-aging, collagen support, preventative purposes.	2026-02-06 00:32:45+00	2026-02-06 00:32:45+00
4466	1653	107	9	f	f	1	Medium Dose. Moderate wrinkles, skin regeneration purposes.	2026-02-06 00:32:45+00	2026-02-06 00:32:45+00
4467	1653	108	9	f	f	2	High Dosage. Ideal for targeted rejuvenation.	2026-02-06 00:32:45+00	2026-02-06 00:32:45+00
4468	1653	109	9	f	f	3	Intensive localized use (e.g., scars, joints)	2026-02-06 00:32:45+00	2026-02-06 00:32:45+00
4469	1654	38	1	f	t	0	Low dose to test response.	2026-02-06 00:33:00+00	2026-02-06 00:33:00+00
4470	1654	39	16	f	f	1	Standard dose. Most commonly used.	2026-02-06 00:33:00+00	2026-02-06 00:33:00+00
4471	1654	40	1	f	f	2	High dose. Intended for intense learning enhancement	2026-02-06 00:33:00+00	2026-02-06 00:33:00+00
4472	1655	117	11	f	t	0	Low dosage. Frequent administration because of short half-life.	2026-02-06 00:33:00+00	2026-02-06 00:33:00+00
4473	1655	155	11	f	f	1	Moderate dosage. Frequent administration because of short half-life.	2026-02-06 00:33:00+00	2026-02-06 00:33:00+00
4474	1655	219	11	f	f	2	Maximum recommended dosage. Frequent administration because of short half-life.	2026-02-06 00:33:00+00	2026-02-06 00:33:00+00
4475	1656	62	1	f	t	0	Low dose. Perfect for testing response or an entry level protocol.	2026-02-06 00:33:16+00	2026-02-06 00:33:16+00
4476	1656	121	1	f	f	1	Moderate dose. Commonly used dosage for research and recreational use.	2026-02-06 00:33:16+00	2026-02-06 00:33:16+00
4477	1656	122	1	f	f	2	High Dose. Ideal for aggressive protocols.	2026-02-06 00:33:16+00	2026-02-06 00:33:16+00
4478	1656	39	12	f	f	3	Pulsed weekly dosing protocol.	2026-02-06 00:33:16+00	2026-02-06 00:33:16+00
4479	1657	35	13	f	t	0	Low dose.	2026-02-06 00:33:33+00	2026-02-06 00:33:33+00
4480	1657	42	13	f	f	1	Medium dose.	2026-02-06 00:33:33+00	2026-02-06 00:33:33+00
4481	1657	75	13	f	f	2	High dose.	2026-02-06 00:33:33+00	2026-02-06 00:33:33+00
4482	1657	81	13	f	f	3	Maximum recommended dose.	2026-02-06 00:33:33+00	2026-02-06 00:33:33+00
4511	1666	120	11	f	t	0	Low very conservative dosing. Useful for testing response.	2026-02-06 00:36:47+00	2026-02-06 00:36:47+00
4512	1666	54	11	f	f	1	Conservative dosing. Recommended for individuals of low bodyweight under 60kg.	2026-02-06 00:36:47+00	2026-02-06 00:36:47+00
4513	1666	55	11	f	f	2	Standard optimal efficacy dosage for an average person about 80kg bodyweight.	2026-02-06 00:36:47+00	2026-02-06 00:36:47+00
4514	1666	228	11	f	f	3	Maximum Recommended Dose. Recommended for people over 100kg bodyweight.	2026-02-06 00:36:47+00	2026-02-06 00:36:47+00
4530	1672	136	13	f	t	0	Low dose for minimal fertility support.	2026-02-06 00:39:43+00	2026-02-06 00:39:43+00
4531	1672	138	13	f	f	1	Medium dose for fertility, hormone and sexual function optimization.	2026-02-06 00:39:43+00	2026-02-06 00:39:43+00
4532	1672	122	13	f	f	2	High dose for maximum effect.	2026-02-06 00:39:43+00	2026-02-06 00:39:43+00
4551	1679	62	9	f	t	0	Low dose. Ideal for testing response.	2026-02-06 00:40:51+00	2026-02-06 00:40:51+00
4552	1679	63	9	f	f	1	Moderate dose. Sweet spot of safety and efficacy.	2026-02-06 00:40:51+00	2026-02-06 00:40:51+00
4553	1679	37	9	f	f	2	High dosage. Intended for aggressive gene modulation.	2026-02-06 00:40:51+00	2026-02-06 00:40:51+00
4554	1679	55	9	f	f	3	Maximum recommended dose.	2026-02-06 00:40:51+00	2026-02-06 00:40:51+00
4555	1680	38	1	f	t	0	Low dose. Starting dose. Titrate up by 500mcg every 1-2 weeks.	2026-02-06 00:40:51+00	2026-02-06 00:40:51+00
4556	1680	54	9	f	f	1	Low end moderate dose. Titrate up by 500mcg every 1-2 weeks if tolerable.	2026-02-06 00:40:51+00	2026-02-06 00:40:51+00
4557	1680	91	1	f	f	2	High end moderate dose. Titrate up by 500mcg every 1-2 weeks if tolerable.	2026-02-06 00:40:51+00	2026-02-06 00:40:51+00
4558	1680	40	1	f	f	3	Maximum recommended dose.	2026-02-06 00:40:51+00	2026-02-06 00:40:51+00
4559	1681	24	8	f	t	0	Subcutaneous injections everyday for 4 weeks, 2 weeks off and then repeat.	2026-02-06 00:41:06+00	2026-02-06 00:41:06+00
4560	1681	1	8	f	f	1	Subcutaneous injections everyday for 4 weeks, 2 weeks off and then repeat.\nLower dosage, can titrate up.	2026-02-06 00:41:06+00	2026-02-06 00:41:06+00
4561	1681	26	9	f	f	2	Twice daily administration for more stable blood concentration.	2026-02-06 00:41:06+00	2026-02-06 00:41:06+00
4562	1681	90	1	f	f	3	Maximum recommended dose.	2026-02-06 00:41:06+00	2026-02-06 00:41:06+00
4563	1682	27	2	f	t	0	Low Concentration. Applied directly to the wound or problematic location.	2026-02-06 00:41:06+00	2026-02-06 00:41:06+00
4564	1682	28	2	f	f	1	Medium Concentration. Applied directly to the wound or problematic location.	2026-02-06 00:41:06+00	2026-02-06 00:41:06+00
4565	1682	29	2	f	f	2	Strong Concentration. Applied directly to the wound or problematic location.	2026-02-06 00:41:06+00	2026-02-06 00:41:06+00
4566	1683	79	12	f	t	0	Titrate up to this dosage by 1.5mg increments every 4 weeks.	2026-02-06 00:41:34+00	2026-02-06 00:41:34+00
4567	1683	80	12	f	f	1	Titrate up to this dosage by a 1.5mg increment after 4 weeks of low dose.	2026-02-06 00:41:34+00	2026-02-06 00:41:34+00
4568	1683	81	12	f	f	2	Titrate up to this dosage by 2mg increments every 4 weeks after medium dosage.	2026-02-06 00:41:34+00	2026-02-06 00:41:34+00
4581	1687	166	1	f	t	0	Low dose. Usually sufficient for most.	2026-02-06 00:44:05+00	2026-02-06 00:44:05+00
4582	1687	176	1	f	f	1	Moderate dose. Significantly more efficacious.	2026-02-06 00:44:05+00	2026-02-06 00:44:05+00
4583	1687	177	1	f	f	2	High Dose. Carb and Protein centered diet is advised.	2026-02-06 00:44:05+00	2026-02-06 00:44:05+00
4584	1687	178	1	f	f	3	Maximum recommended dose.	2026-02-06 00:44:05+00	2026-02-06 00:44:05+00
4597	1691	22	1	f	t	0	Low dose. Useful to test tolerance and is sustainable long-term.	2026-02-06 00:46:11+00	2026-02-06 00:46:11+00
4598	1691	30	1	f	f	1	Medium dose. Useful for stronger effect.	2026-02-06 00:46:11+00	2026-02-06 00:46:11+00
4599	1691	31	1	f	f	2	High dose. For Intense mitochondrial support.	2026-02-06 00:46:11+00	2026-02-06 00:46:11+00
4600	1691	105	1	f	f	3	Very high dose for intense mitochondrial support	2026-02-06 00:46:11+00	2026-02-06 00:46:11+00
4601	1691	158	1	f	f	4	Maximum recommended dose.	2026-02-06 00:46:11+00	2026-02-06 00:46:11+00
4602	1692	35	1	f	t	0	Low dose. Useful to test tolerance and is sustainable long-term.	2026-02-06 00:46:11+00	2026-02-06 00:46:11+00
4603	1692	23	9	f	f	1	Medium dose. Useful for stronger effect. Divided dosage for more stable blood and brain concentrations.	2026-02-06 00:46:11+00	2026-02-06 00:46:11+00
4604	1692	30	1	f	f	2	Medium dose. Useful for stronger effect. Single dose for ease of use.	2026-02-06 00:46:11+00	2026-02-06 00:46:11+00
4605	1692	40	11	f	f	3	Low end of High dose. More spread out for better tolerance and more stable blood and brain concentrations.	2026-02-06 00:46:11+00	2026-02-06 00:46:11+00
4606	1692	41	11	f	f	4	High end of High dose. More spread out for better tolerance and more stable blood and brain concentrations.	2026-02-06 00:46:11+00	2026-02-06 00:46:11+00
4607	1693	223	9	f	t	0	Minimal effective concentration. Effective for anti-aging and wound healing.	2026-02-06 00:46:11+00	2026-02-06 00:46:11+00
4608	1693	224	11	f	f	1	Moderate concentration. Most commonly utilized. Effective for anti-aging and wound healing.	2026-02-06 00:46:11+00	2026-02-06 00:46:11+00
4609	1693	225	11	f	f	2	High concentration. Most optimal for both anti-aging and wound healing purposes.	2026-02-06 00:46:11+00	2026-02-06 00:46:11+00
4616	1696	102	14	f	t	0	Lowest practical dose.	2026-02-06 00:47:06+00	2026-02-06 00:47:06+00
4617	1696	77	9	f	f	1	Moderate dose. Most commonly used.	2026-02-06 00:47:06+00	2026-02-06 00:47:06+00
4618	1696	31	11	f	f	2	High dose for aggressive results.	2026-02-06 00:47:06+00	2026-02-06 00:47:06+00
4624	1699	1	1	f	t	0	Low dose. Sustainable approach for cognitive decline, anti-aging and tumor suppresion.	2026-02-06 01:03:18+00	2026-02-06 01:03:18+00
4625	1699	2	1	f	f	1	Standard dose. Sustainable approach for cognitive decline, anti-aging and tumor suppresion.	2026-02-06 01:03:18+00	2026-02-06 01:03:18+00
4626	1699	37	1	f	f	2	High Dose. Costly but also a sustainable approach for cognitive decline, anti-aging and tumor suppresion.	2026-02-06 01:03:18+00	2026-02-06 01:03:18+00
4627	1700	38	1	f	t	0	Low dose. Sustainable approach for cognitive decline, anti-aging and tumor suppresion.	2026-02-06 01:03:18+00	2026-02-06 01:03:18+00
4628	1700	39	1	f	f	1	High end of Low dose. Sustainable approach for cognitive decline, anti-aging and tumor suppresion.	2026-02-06 01:03:18+00	2026-02-06 01:03:18+00
4629	1700	40	1	f	f	2	Standard dose. Sustainable approach for cognitive decline, anti-aging and tumor suppresion.	2026-02-06 01:03:18+00	2026-02-06 01:03:18+00
4630	1700	41	1	f	f	3	High Dose. Costly but also a sustainable approach for cognitive decline, anti-aging and tumor suppresion.	2026-02-06 01:03:18+00	2026-02-06 01:03:18+00
4631	1701	102	1	f	t	0	Low, Prophylactic dose. Perfect for preventing pancreatic decline and metabolic support in mild conditions.	2026-02-06 01:03:35+00	2026-02-06 01:03:35+00
4632	1701	77	9	f	f	1	Moderate, Therapeutic dose. Perfect for Insulin resistance management under blood glucose monitoring or chronic pancreatitis.	2026-02-06 01:03:35+00	2026-02-06 01:03:35+00
4633	1701	105	9	f	f	2	Intense Therapeutic dose. Higher efficacy than moderate, but the same usecase.	2026-02-06 01:03:35+00	2026-02-06 01:03:35+00
4634	1702	102	12	f	t	0	Low, Prophylactic dose. Perfect for preventing pancreatic decline and metabolic support in mild conditions.	2026-02-06 01:03:35+00	2026-02-06 01:03:35+00
4785	1746	23	7	f	t	0	Ideal Subcutaneous Dosing Protocol.	2026-02-18 22:38:36+00	2026-02-18 22:38:36+00
4635	1702	77	2	f	f	1	Moderate, Therapeutic dose. Perfect for Insulin resistance management under blood glucose monitoring or chronic pancreatitis.	2026-02-06 01:03:35+00	2026-02-06 01:03:35+00
4636	1702	78	13	f	f	2	Intense Therapeutic dose. Higher efficacy than moderate, but the same usecase.	2026-02-06 01:03:35+00	2026-02-06 01:03:35+00
4637	1703	62	1	f	t	0	Once daily injection in the morning. Low dosage.	2026-02-06 01:03:49+00	2026-02-06 01:03:49+00
4638	1703	63	1	f	f	1	Once daily injection in the morning. Low-end Medium dosage.	2026-02-06 01:03:49+00	2026-02-06 01:03:49+00
4639	1703	54	1	f	f	2	Once daily injection in the morning. High-end Medium dosage.	2026-02-06 01:03:49+00	2026-02-06 01:03:49+00
4640	1703	55	1	f	f	3	Once daily injection in the morning. High dosage.	2026-02-06 01:03:49+00	2026-02-06 01:03:49+00
4641	1704	62	1	f	t	0	Once daily or split up intranasal administration (sprays).	2026-02-06 01:03:49+00	2026-02-06 01:03:49+00
4642	1704	63	1	f	f	1	Once daily or split up intranasal administration (sprays).	2026-02-06 01:03:49+00	2026-02-06 01:03:49+00
4643	1704	37	1	f	f	2	Once daily or split up intranasal administration (sprays).	2026-02-06 01:03:49+00	2026-02-06 01:03:49+00
4647	1706	35	1	f	t	0	Low dose. Cheap and effective.	2026-02-06 01:04:29+00	2026-02-06 01:04:29+00
4648	1706	42	1	f	f	1	Moderate dose. Significantly more efficacious without significant drawbacks besides price. Can be split up through out the day.	2026-02-06 01:04:29+00	2026-02-06 01:04:29+00
4649	1706	110	1	f	f	2	High dose. Significantly more efficacious without significant drawbacks besides price. Can be split up through out the day.	2026-02-06 01:04:29+00	2026-02-06 01:04:29+00
4650	1707	62	13	f	t	0	Low dose. Useful for testing response.	2026-02-06 01:04:58+00	2026-02-06 01:04:58+00
4651	1707	71	13	f	f	1	Moderate dose. Most common anecdotal dosage used.	2026-02-06 01:04:58+00	2026-02-06 01:04:58+00
4652	1707	146	13	f	f	2	High dose. Highest anecdotal dosage of relevance.	2026-02-06 01:04:58+00	2026-02-06 01:04:58+00
4653	1707	221	13	f	f	3	Low-end of extrapolative dosage from animal studies. Purely hypothetical for educative purposes.	2026-02-06 01:04:58+00	2026-02-06 01:04:58+00
4654	1707	222	13	f	f	4	High-end of extrapolative dosage from animal studies. Purely hypothetical for educative purposes.	2026-02-06 01:04:58+00	2026-02-06 01:04:58+00
4670	1714	238	9	f	t	0	Mild concentration for safe and mild effects.	2026-02-06 01:06:32+00	2026-02-06 01:06:32+00
4671	1714	239	9	f	f	1	Moderate concentration appropriate for most users.	2026-02-06 01:06:32+00	2026-02-06 01:06:32+00
4672	1714	240	9	f	f	2	High concentration that is rarely necessary.	2026-02-06 01:06:32+00	2026-02-06 01:06:32+00
4673	1715	85	12	f	t	0	Low dose to test the grounds. Titrate up to this in 150mcg increments weekly.	2026-02-06 01:06:45+00	2026-02-06 01:06:45+00
4674	1715	86	12	f	f	1	Medium dose, usual dose in trials. Titrate up to this in 300mcg increments biweekly.	2026-02-06 01:06:45+00	2026-02-06 01:06:45+00
4675	1715	226	12	f	f	2	High-moderate dose, middle ground between maximum and moderate efficacy. Titrate up to this in 300mcg increments biweekly.	2026-02-06 01:06:45+00	2026-02-06 01:06:45+00
4676	1715	87	12	f	f	3	High dose, maximum well tolerated. Titrate up to this in 300mcg increments biweekly.	2026-02-06 01:06:45+00	2026-02-06 01:06:45+00
4685	1718	1	1	f	t	0	Low dose. Useful to test response,	2026-02-06 01:07:35+00	2026-02-06 01:07:35+00
4686	1718	139	1	f	f	1	Medium dose for a decent fertility and hormone production boost.	2026-02-06 01:07:35+00	2026-02-06 01:07:35+00
4687	1718	140	1	f	f	2	High dose for maximum fertility or hormone production	2026-02-06 01:07:35+00	2026-02-06 01:07:35+00
4688	1719	76	1	f	t	0	Low dose. Effective for immune support, however is otherwise ideal for testing response.	2026-02-06 01:07:57+00	2026-02-06 01:07:57+00
4689	1719	77	1	f	f	1	Moderate dose. Significantly greater efficacy.	2026-02-06 01:07:58+00	2026-02-06 01:07:58+00
4690	1719	81	9	f	f	2	Maximum recommended dose. More frequent injections recommended.	2026-02-06 01:07:58+00	2026-02-06 01:07:58+00
4691	1720	76	1	f	t	0	Low dose. Effective for immune support and to a low degree anti-aging, however is otherwise ideal for testing response.	2026-02-06 01:07:58+00	2026-02-06 01:07:58+00
4692	1720	30	9	f	f	1	Moderate dose. Significantly greater efficacy. If possible recommended to split the dose up even further into as frequent administration as personally comfortable	2026-02-06 01:07:58+00	2026-02-06 01:07:58+00
4693	1720	81	9	f	f	2	Maximum recommended dose. If possible recommended to split the dose up even further into as frequent administration as personally comfortable.	2026-02-06 01:07:58+00	2026-02-06 01:07:58+00
4694	1721	38	2	f	t	0	Low dose. Good for mild immune enhancement or maintenance	2026-02-06 01:08:11+00	2026-02-06 01:08:11+00
4695	1721	91	2	f	f	1	Medium dose. Most often used for standard clinical/research use like HBV, COVID-19.	2026-02-06 01:08:11+00	2026-02-06 01:08:11+00
4696	1721	92	2	f	f	2	High dose. Mostly used for as cancer adjuvant therapy, immune suppression.	2026-02-06 01:08:11+00	2026-02-06 01:08:11+00
4697	1721	41	2	f	f	3	Low end of extreme dosages. Twice weekly so can be maintained longer. Keep it reserved for acute illness or severe immune dysregulation.	2026-02-06 01:08:11+00	2026-02-06 01:08:11+00
4698	1721	41	1	f	f	4	Low end of acute extreme protocol. Daily so only run a short cycle. Keep it reserved for acute illness or severe immune dysregulation.	2026-02-06 01:08:11+00	2026-02-06 01:08:11+00
4699	1721	94	2	f	f	5	High end of extreme dosages. Twice weekly so can be maintained longer. Keep it reserved for acute illness or severe immune dysregulation.	2026-02-06 01:08:11+00	2026-02-06 01:08:11+00
4700	1721	94	1	f	f	6	The most extreme acute protocol. Daily so only run a short cycle. Keep it reserved for extreme acute illness or severe immune dysregulation.	2026-02-06 01:08:11+00	2026-02-06 01:08:11+00
4701	1722	232	9	f	t	0	Minimal concentration prescribed clinically.	2026-02-06 01:08:23+00	2026-02-06 01:08:23+00
4702	1722	233	9	f	f	1	More experimental enhanced concentration that anecdotally provides much better results.	2026-02-06 01:08:23+00	2026-02-06 01:08:23+00
4703	1722	234	9	f	f	2	Maximum experimental concentration.	2026-02-06 01:08:23+00	2026-02-06 01:08:23+00
4704	1723	102	1	f	t	0	Low dose. Cheap and effective. Good for testing response or conservative maintenance protocol.	2026-02-06 01:08:35+00	2026-02-06 01:08:35+00
4705	1723	77	9	f	f	1	Moderate dose. Significantly more effective without significant drawbacks.	2026-02-06 01:08:35+00	2026-02-06 01:08:35+00
4706	1723	81	11	f	f	2	 High dose. Therapeutic or heavy rejuvenation or cardiovascular treatment.	2026-02-06 01:08:35+00	2026-02-06 01:08:35+00
4707	1723	111	1	f	f	3	Maximum recommendable dosage. Split to preferred frequency.	2026-02-06 01:08:35+00	2026-02-06 01:08:35+00
4708	1724	38	1	f	t	0	Low dose. Cheap and effective. Good for testing response or conservative maintenance protocol.	2026-02-06 01:08:35+00	2026-02-06 01:08:35+00
4709	1724	227	1	f	f	1	Moderate dose. Significantly more effective without significant drawbacks.	2026-02-06 01:08:35+00	2026-02-06 01:08:35+00
4710	1724	40	1	f	f	2	High dose. Top range of researched dosages. 	2026-02-06 01:08:35+00	2026-02-06 01:08:35+00
4711	1725	76	1	f	t	0	Low dose. Ideal for testing response.	2026-02-06 01:08:45+00	2026-02-06 01:08:45+00
4712	1725	30	9	f	f	1	Moderate dose. Sweet spot for Longevity, Immune support and Regeneration goals.	2026-02-06 01:08:45+00	2026-02-06 01:08:45+00
4713	1725	81	9	f	f	2	High dose. Most efficacious by far, but most risk for side-effects.	2026-02-06 01:08:45+00	2026-02-06 01:08:45+00
4714	1726	76	1	f	t	0	Low dose. Ideal for testing response.	2026-02-06 01:08:45+00	2026-02-06 01:08:45+00
4715	1726	30	1	f	f	1	Moderate dose. Sweet spot for Longevity, Immune support and Regeneration goals.	2026-02-06 01:08:45+00	2026-02-06 01:08:45+00
4716	1726	81	9	f	f	2	High dose. Most efficacious by far, but most risk for side-effects.	2026-02-06 01:08:45+00	2026-02-06 01:08:45+00
4717	1726	81	11	f	f	3	Maximum dose. Short-Term bursts only as a safety precaution.	2026-02-06 01:08:45+00	2026-02-06 01:08:45+00
4729	1730	38	2	t	t	0	Weekly injection for weight management - start low and titrate roughly every 4 weeks.	2026-02-18 22:17:33+00	2026-02-18 22:17:33+00
4730	1730	22	2	f	f	1	Second titration dosage. Efficacy still minimal.	2026-02-18 22:17:33+00	2026-02-18 22:17:33+00
4731	1730	64	2	f	f	2	Moderate efficacy dosage. If insufficient titrate up.	2026-02-18 22:17:33+00	2026-02-18 22:17:33+00
4732	1730	157	2	f	f	3	Most common maintenance dosage. Moderate-High efficacy.	2026-02-18 22:17:33+00	2026-02-18 22:17:33+00
4733	1730	94	2	f	f	4	Maximum recommended dosage. Usually reserved for clinical obesity.	2026-02-18 22:17:33+00	2026-02-18 22:17:33+00
4734	1731	48	9	f	t	0	Low dose. Useful to test tolerance.	2026-02-18 22:18:28+00	2026-02-18 22:18:28+00
4735	1731	49	9	f	f	1	Medium/Maintenance dose.	2026-02-18 22:18:28+00	2026-02-18 22:18:28+00
4736	1731	49	11	f	f	2	Standard dose for optimal efficacy. More frequent doses for more stable levels. Good for strict regimens.	2026-02-18 22:18:28+00	2026-02-18 22:18:28+00
4737	1731	50	11	f	f	3	High dose. For extreme usage.	2026-02-18 22:18:28+00	2026-02-18 22:18:28+00
4738	1732	51	9	f	t	0	Low dose. Useful to test tolerance or for a mild NAD+ boost.	2026-02-18 22:18:28+00	2026-02-18 22:18:28+00
4739	1732	52	9	f	f	1	Medium/Maintenance dose. Most commonly used and usually more than sufficient.	2026-02-18 22:18:28+00	2026-02-18 22:18:28+00
4740	1732	53	9	f	f	2	Maximum dose. For very extreme usage.	2026-02-18 22:18:28+00	2026-02-18 22:18:28+00
4741	1733	120	1	f	t	0	Low dose to assess response or for long term cartilage repair.	2026-02-18 22:21:10+00	2026-02-18 22:21:10+00
4742	1733	71	1	f	f	1	Medium dose, useful for sustained long term fat loss.	2026-02-18 22:21:10+00	2026-02-18 22:21:10+00
4743	1733	145	1	f	f	2	Moderately enhanced dose for more potent fat loss.	2026-02-18 22:21:10+00	2026-02-18 22:21:10+00
4744	1733	37	1	f	f	3	Maximum recommended dose for most pronounced fat loss.	2026-02-18 22:21:10+00	2026-02-18 22:21:10+00
4745	1734	2	1	f	t	0	Standard Daily Injection. IM or SubQ	2026-02-18 22:26:35+00	2026-02-18 22:26:35+00
4746	1734	21	7	f	f	1	Low dose Frequent Injection method. Ideal for Stable Blood Concentration. Ideally go with SubQ injection for slow release.	2026-02-18 22:26:35+00	2026-02-18 22:26:35+00
4747	1734	200	7	f	f	2	Moderate dose Frequent Injection method.  Ideal for Stable Blood Concentration. Ideally go with SubQ injection for slow release.	2026-02-18 22:26:35+00	2026-02-18 22:26:35+00
4748	1734	201	7	f	f	3	High dose Frequent Injection method. Ideal for Stable Blood Concentration. Ideally go with SubQ injection for slow release. The most powerful and optimal systemic protocol.	2026-02-18 22:26:35+00	2026-02-18 22:26:35+00
4749	1734	54	1	f	f	4	Medium dosage for localized injection near injury. Still has the same systemic effects, but if injected close to the injury intramuscularly then has additionally temporarily increased localized effect.	2026-02-18 22:26:35+00	2026-02-18 22:26:35+00
4750	1734	203	1	f	f	5	High dosage for localized injection near injury. Still has the same systemic effects, but if injected close to the injury intramuscularly then has additionally temporarily increased localized effect.	2026-02-18 22:26:35+00	2026-02-18 22:26:35+00
4751	1735	72	1	f	t	0	Standard dose for IBS, Ulcers, Hiatal hernias.	2026-02-18 22:26:35+00	2026-02-18 22:26:35+00
4752	1736	131	9	f	t	0	Low concentration cream. Perfect for inor cuts, skin irritation, post-laser recovery.	2026-02-18 22:26:35+00	2026-02-18 22:26:35+00
4753	1736	132	9	f	f	1	Moderate dose. Perfect for moderate burns, dermal abrasions, stubborn wounds, inflammation, eczema or rosacea flare ups.	2026-02-18 22:26:35+00	2026-02-18 22:26:35+00
4754	1736	133	9	f	f	2	High concentration, typically intended for deep tissue injury, chronic non-healing wounds, stretch marks, surgical recovery.	2026-02-18 22:26:35+00	2026-02-18 22:26:35+00
4755	1737	51	1	f	t	0	Low dose. Test response and titrate until appropriate efficacy.	2026-02-18 22:28:25+00	2026-02-18 22:28:25+00
4756	1737	173	1	f	f	1	Moderate dose. Most commonly used with significant efficacy.	2026-02-18 22:28:25+00	2026-02-18 22:28:25+00
4757	1737	174	1	f	f	2	Maximum recommended dose.	2026-02-18 22:28:25+00	2026-02-18 22:28:25+00
4758	1738	102	1	f	t	0	Low dose. Test response and titrate up.	2026-02-18 22:28:25+00	2026-02-18 22:28:25+00
4759	1738	126	1	f	f	1	Moderate dose. Most commonly used.	2026-02-18 22:28:25+00	2026-02-18 22:28:25+00
4760	1738	127	1	f	f	2	Maximum recommended oral dose.	2026-02-18 22:28:25+00	2026-02-18 22:28:25+00
4764	1740	22	12	t	t	0	Weekly injection for sustained GH release	2026-02-18 22:33:54+00	2026-02-18 22:33:54+00
4765	1740	23	12	f	f	1	Higher weekly dose for enhanced effects	2026-02-18 22:33:54+00	2026-02-18 22:33:54+00
4766	1740	41	12	f	f	2	Very aggressive dose for extreme results.	2026-02-18 22:33:54+00	2026-02-18 22:33:54+00
4767	1741	62	9	f	t	0	Lowest effective protocol.	2026-02-18 22:34:16+00	2026-02-18 22:34:16+00
4768	1741	62	11	f	f	1	Optimal lowest dosage protocol.	2026-02-18 22:34:16+00	2026-02-18 22:34:16+00
4769	1741	204	11	f	f	2	Standard protocol. Very tolerable, cost-effective and efficacious. Ideally combined with ghrelin receptor agonists for very potent synergy.	2026-02-18 22:34:16+00	2026-02-18 22:34:16+00
4770	1741	122	11	f	f	3	Intensive dosing protocol. Still generally very tolerable, but more likely to cause side effects. Has the most potent efficacy. Ideally combined with ghrelin receptor agonists for a very potent synergy.	2026-02-18 22:34:16+00	2026-02-18 22:34:16+00
4771	1742	35	1	f	t	0	Low dose, good to test it's effects and have sustainable neurogenesis. Little risk for aberrant synaptogenesis.	2026-02-18 22:35:08+00	2026-02-18 22:35:08+00
4772	1742	30	1	f	f	1	Medium dose. Middle ground, sustainable and effective. Advisable to be productive to avoid aberrant synaptogenesis.	2026-02-18 22:35:08+00	2026-02-18 22:35:08+00
4773	1742	31	1	f	f	2	High dose. Best utilized with intense stimulus. Otherwise can cause aberrant synaptogenesis.\n\n	2026-02-18 22:35:08+00	2026-02-18 22:35:08+00
4774	1742	78	1	f	f	3	Maximum recommended dose.	2026-02-18 22:35:08+00	2026-02-18 22:35:08+00
4775	1743	22	1	f	f	0	Low and sustainable approach. 	2026-02-18 22:35:08+00	2026-02-18 22:35:08+00
4776	1743	35	1	f	f	1	Slightly higher dose, but still sustainable.	2026-02-18 22:35:08+00	2026-02-18 22:35:08+00
4777	1743	30	8	f	f	2	Medium dosage. Advisable to be productive to avoid aberrant synaptogenesis.	2026-02-18 22:35:08+00	2026-02-18 22:35:08+00
4778	1743	31	1	f	f	3	High dose. Best utilized with intense stimulus. Otherwise can cause aberrant synaptogenesis.	2026-02-18 22:35:08+00	2026-02-18 22:35:08+00
4779	1744	1	1	t	t	0	Daily injection 30-60 minutes before bedtime	2026-02-18 22:36:07+00	2026-02-18 22:36:07+00
4780	1744	139	1	f	f	1	Moderate dose. Daily injection 30-60 minutes before bedtime	2026-02-18 22:36:07+00	2026-02-18 22:36:07+00
4781	1744	140	1	f	f	2	High dose. Daily injection 30-60 minutes before bedtime	2026-02-18 22:36:07+00	2026-02-18 22:36:07+00
4782	1745	1	1	t	t	0	Nasal spray before bedtime for sleep improvement	2026-02-18 22:36:07+00	2026-02-18 22:36:07+00
4783	1745	139	1	f	f	1	Moderate dose. Nasal spray before bedtime for sleep improvement	2026-02-18 22:36:07+00	2026-02-18 22:36:07+00
4784	1745	140	1	f	f	2	High dose. Nasal spray before bedtime for sleep improvement.	2026-02-18 22:36:07+00	2026-02-18 22:36:07+00
4849	1765	153	1	f	f	2	High end oral dose.	2026-02-18 22:46:25+00	2026-02-18 22:46:25+00
4786	1746	30	9	f	f	1	Middle ground between frequent injections and high dose.	2026-02-18 22:38:36+00	2026-02-18 22:38:36+00
4787	1746	31	1	f	f	2	Not optimal, but easy to manage.	2026-02-18 22:38:36+00	2026-02-18 22:38:36+00
4788	1746	22	9	f	f	3	Low dose, budget friendly and sustainable.	2026-02-18 22:38:36+00	2026-02-18 22:38:36+00
4789	1746	31	7	f	f	4	Extreme dosing protocol of high dose and frequent injections. Up to thrice daily. Zinc supplementation is advisable. 	2026-02-18 22:38:36+00	2026-02-18 22:38:36+00
4790	1747	32	9	f	t	0	Low concentration for sensitive skin.	2026-02-18 22:38:36+00	2026-02-18 22:38:36+00
4791	1747	33	9	f	f	1	Medium Concentration for most Skin types.	2026-02-18 22:38:36+00	2026-02-18 22:38:36+00
4792	1747	34	9	f	f	2	Strong Concentration. Perfect for boosting collagen production and quality.	2026-02-18 22:38:36+00	2026-02-18 22:38:36+00
4793	1748	62	11	f	t	0	Low dose. 1-3 times a day.	2026-02-18 22:39:09+00	2026-02-18 22:39:09+00
4794	1748	139	11	f	f	1	Medium dose. 1-3 times a day.	2026-02-18 22:39:09+00	2026-02-18 22:39:09+00
4795	1748	140	11	f	f	2	High dose. 1-3 times a day.	2026-02-18 22:39:09+00	2026-02-18 22:39:09+00
4796	1749	62	11	f	t	0	Low dose. 1-3 times a day.	2026-02-18 22:39:42+00	2026-02-18 22:39:42+00
4797	1749	139	11	f	f	1	Medium dose. 1-3 times a day.	2026-02-18 22:39:42+00	2026-02-18 22:39:42+00
4798	1749	140	11	f	f	2	High dose. 1-3 times a day.	2026-02-18 22:39:42+00	2026-02-18 22:39:42+00
4799	1750	51	1	f	t	0	Very low dose. Only really useful to test response.	2026-02-18 22:40:14+00	2026-02-18 22:40:14+00
4800	1750	113	1	f	f	1	Standard dose. Most commonly used. Decent, albeit limited, benefits at low cost.	2026-02-18 22:40:14+00	2026-02-18 22:40:14+00
4801	1750	53	1	f	f	2	High Dose. Metabolic and performance enhancing benefits get really pronounced around this dose.	2026-02-18 22:40:14+00	2026-02-18 22:40:14+00
4802	1750	179	1	f	f	3	Metabolic and performance enhancing benefits reach their peak efficiency roughly here. Going higher is not recommended.	2026-02-18 22:40:14+00	2026-02-18 22:40:14+00
4803	1751	2	13	t	t	0	Theoretically Ideal HCG protocol For Hormone Status - thrice weekly subcutaneous injection	2026-02-18 22:40:45+00	2026-02-18 22:40:45+00
4804	1751	72	13	f	f	1	Maximum fertility protocol.	2026-02-18 22:40:45+00	2026-02-18 22:40:45+00
4805	1751	25	16	f	f	2	Twice a year cycle to protect against the possibility of testicular atrophy while using TRT.	2026-02-18 22:40:45+00	2026-02-18 22:40:45+00
4806	1752	136	9	f	t	0	Once or Twice daily. Minimal effective dose to test the response or for chronic low dosage use.	2026-02-18 22:41:16+00	2026-02-18 22:41:16+00
4807	1752	62	9	f	f	1	Once or Twice daily. Low dose for chronic low dosage use.	2026-02-18 22:41:16+00	2026-02-18 22:41:16+00
4808	1752	138	11	f	f	2	Once to Thrice Daily. Moderate, heavily researched and noticeably effective dose. 	2026-02-18 22:41:16+00	2026-02-18 22:41:16+00
4809	1752	122	11	f	f	3	Once to Thrice daily. Intensive dosing protocol reserved for users with experience and understanding of the compound.	2026-02-18 22:41:16+00	2026-02-18 22:41:16+00
4810	1753	120	1	f	t	0	Low dose. Commonly used by beginners or for a slow weight-loss plan.	2026-02-18 22:42:10+00	2026-02-18 22:42:10+00
4811	1753	63	9	f	f	1	Moderate dose. Most common protocol.	2026-02-18 22:42:10+00	2026-02-18 22:42:10+00
4812	1753	37	9	f	f	2	Aggressive dose. Typically used pre-contest.	2026-02-18 22:42:10+00	2026-02-18 22:42:10+00
4813	1754	96	13	f	t	0	Standard dose for male fertility and testosterone production. Should be combined with HCG.	2026-02-18 22:42:40+00	2026-02-18 22:42:40+00
4814	1754	95	13	f	f	1	Standard dose for female fertility.	2026-02-18 22:42:40+00	2026-02-18 22:42:40+00
4815	1754	98	13	f	f	2	High-end dose for male fertility and testosterone production. Should be combined with HCG.	2026-02-18 22:42:40+00	2026-02-18 22:42:40+00
4816	1754	97	13	f	f	3	High-end dose for female fertility.	2026-02-18 22:42:40+00	2026-02-18 22:42:40+00
4817	1755	82	9	f	t	0	Low dose. Twice daily due to short half life.	2026-02-18 22:43:25+00	2026-02-18 22:43:25+00
4818	1755	83	9	f	f	1	Medium dose. Twice daily due to short half life.	2026-02-18 22:43:25+00	2026-02-18 22:43:25+00
4819	1755	84	9	f	f	2	High Dose. Twice daily due to short half life.	2026-02-18 22:43:25+00	2026-02-18 22:43:25+00
4820	1755	179	9	f	f	3	Maximum Recommended Dose. Twice daily due to short half life.	2026-02-18 22:43:25+00	2026-02-18 22:43:25+00
4821	1756	82	9	f	t	0	Low dose. Twice daily due to short half life.	2026-02-18 22:43:25+00	2026-02-18 22:43:25+00
4822	1756	83	9	f	f	1	Medium dose. Twice daily due to short half life.	2026-02-18 22:43:25+00	2026-02-18 22:43:25+00
4823	1756	84	9	f	f	2	High dose. Twice daily due to short half life.	2026-02-18 22:43:25+00	2026-02-18 22:43:25+00
4824	1757	48	1	f	t	0	Low dose for a little Insulin Sensitivity and Cell Splicing boost.	2026-02-18 22:43:54+00	2026-02-18 22:43:54+00
4825	1757	46	1	f	f	1	Medium dose for a moderate Insulin Sensitivity and Cell Splicing boost.	2026-02-18 22:43:54+00	2026-02-18 22:43:54+00
4826	1757	47	1	f	f	2	High dose for a optimal Insulin Sensitivity and Cell Splicing boost.	2026-02-18 22:43:54+00	2026-02-18 22:43:54+00
4827	1758	21	9	f	t	0	Lower dosage that's easier to stick to.	2026-02-18 22:43:54+00	2026-02-18 22:43:54+00
4828	1758	21	11	f	f	1	Higher, more Discipline requiring dosage.	2026-02-18 22:43:54+00	2026-02-18 22:43:54+00
4829	1759	1	11	t	t	0	Low dose thrice daily injection ideally aimed pre/post workout and before bed for slightly increased GH release	2026-02-18 22:44:56+00	2026-02-18 22:44:56+00
4830	1759	139	11	f	f	1	Higher dose for enhanced GH stimulation	2026-02-18 22:44:56+00	2026-02-18 22:44:56+00
4831	1759	140	11	f	f	2	Maximum recommended dose.	2026-02-18 22:44:56+00	2026-02-18 22:44:56+00
4832	1760	1	1	t	t	0	Low dose daily injection for systemic anti-inflammatory effects	2026-02-18 22:45:43+00	2026-02-18 22:45:43+00
4833	1760	71	1	f	f	1	Higher dose for inflammatory conditions	2026-02-18 22:45:43+00	2026-02-18 22:45:43+00
4834	1760	37	1	f	f	2	Maximum daily dosage for autoimmune disease management.	2026-02-18 22:45:43+00	2026-02-18 22:45:43+00
4835	1761	2	1	t	t	0	Daily oral for IBD and digestive inflammation	2026-02-18 22:45:43+00	2026-02-18 22:45:43+00
4836	1761	3	1	f	f	1	Higher oral dose for severe cases	2026-02-18 22:45:43+00	2026-02-18 22:45:43+00
4837	1762	56	1	t	t	0	Apply to affected skin areas 2-3 times daily	2026-02-18 22:45:43+00	2026-02-18 22:45:43+00
4838	1762	107	11	f	f	1	Moderate concentration for chronic inflammatory/autoimmune skin conditions.	2026-02-18 22:45:43+00	2026-02-18 22:45:43+00
4839	1762	206	11	f	f	2	High concentration for severe chronic inflammatory/autoimmune skin conditions.	2026-02-18 22:45:43+00	2026-02-18 22:45:43+00
4840	1763	2	9	f	t	0	Intranasal administration for high bioavailability non-invasively or for nasal inflammation.	2026-02-18 22:45:43+00	2026-02-18 22:45:43+00
4841	1763	37	11	f	f	1	Intranasal administration for high bioavailability non-invasively or for chronic/severe nasal inflammation.	2026-02-18 22:45:43+00	2026-02-18 22:45:43+00
4842	1764	148	1	t	t	0	Low daily dose.	2026-02-18 22:46:25+00	2026-02-18 22:46:25+00
4843	1764	149	1	f	f	1	Standard Daily dose. Or a high-end maintenance dose after loading.	2026-02-18 22:46:25+00	2026-02-18 22:46:25+00
4844	1764	149	13	f	f	2	Standard maintenance dose after a loading phase.	2026-02-18 22:46:25+00	2026-02-18 22:46:25+00
4845	1764	150	14	f	f	3	Low end Loading phase for 2-4 weeks. Continue with maintenance dose after.	2026-02-18 22:46:25+00	2026-02-18 22:46:25+00
4846	1764	151	14	f	f	4	Intense loading dose for 2-4 weeks. Continue with maintenance dose after.	2026-02-18 22:46:25+00	2026-02-18 22:46:25+00
4847	1765	148	14	f	t	0	Low Oral Dose	2026-02-18 22:46:25+00	2026-02-18 22:46:25+00
4848	1765	152	1	f	f	1	Standard oral dose.	2026-02-18 22:46:25+00	2026-02-18 22:46:25+00
4850	1766	59	9	f	t	0	Standard tanning dose.	2026-02-18 22:47:02+00	2026-02-18 22:47:02+00
4851	1766	160	9	f	f	1	Enhanced tanning dose.	2026-02-18 22:47:02+00	2026-02-18 22:47:02+00
4852	1766	161	1	f	f	2	Tan maintenance.	2026-02-18 22:47:02+00	2026-02-18 22:47:02+00
4853	1766	59	1	f	f	3	Photoprotection with minor tanning.	2026-02-18 22:47:02+00	2026-02-18 22:47:02+00
4854	1767	1	1	t	t	0	Start with low dose daily, gradually increase as needed for tanning	2026-02-18 22:47:28+00	2026-02-18 22:47:28+00
4855	1767	2	1	f	f	1	Standard tanning or low pre-sexual activity dose.	2026-02-18 22:47:28+00	2026-02-18 22:47:28+00
4856	1767	54	13	f	f	2	Standard pre-sexual activity dose or Tan maintenance.	2026-02-18 22:47:28+00	2026-02-18 22:47:28+00
4857	1767	55	1	f	f	3	Maximal dosage for pre-sexual activity.	2026-02-18 22:47:28+00	2026-02-18 22:47:28+00
4858	1768	38	1	t	t	0	Starting dose.	2026-02-18 22:47:28+00	2026-02-18 22:47:28+00
4859	1768	39	1	f	f	1	Standard tanning or pre-sexual activity dose.	2026-02-18 22:47:28+00	2026-02-18 22:47:28+00
4860	1768	40	1	f	f	2	Intense tanning or pre-sexual activity dose.	2026-02-18 22:47:28+00	2026-02-18 22:47:28+00
4861	1768	39	13	f	f	3	Tan maintenance dose.	2026-02-18 22:47:28+00	2026-02-18 22:47:28+00
4862	1769	102	1	f	t	0	Low dose. Very specific, but effective for optimizing the electron transfer chain.	2026-02-18 22:48:30+00	2026-02-18 22:48:30+00
4863	1769	113	1	f	f	1	Medium dose. More potent dose for optimizing the electron transfer chain.	2026-02-18 22:48:30+00	2026-02-18 22:48:30+00
4864	1769	53	1	f	f	2	High dose. Starts stepping into MAO inhibition and acetylcholinesterase inhibition.	2026-02-18 22:48:30+00	2026-02-18 22:48:30+00
4865	1769	50	1	f	f	3	High dose overall. Low antidepressant range dose.	2026-02-18 22:48:30+00	2026-02-18 22:48:30+00
4866	1769	127	16	f	f	4	Very high dose overall. Medium antidepressant range dose.	2026-02-18 22:48:30+00	2026-02-18 22:48:30+00
4867	1769	159	1	f	f	5	Maximum recommended dose.	2026-02-18 22:48:30+00	2026-02-18 22:48:30+00
4868	1770	51	1	f	t	0	Low dose. Most useful as an appetite stimulant.	2026-02-18 22:49:04+00	2026-02-18 22:49:04+00
4869	1770	113	1	f	f	1	Moderate dose. Very commonly used.	2026-02-18 22:49:04+00	2026-02-18 22:49:04+00
4870	1770	116	1	f	f	2	High dose. Used when seeking a substantial GH increase.	2026-02-18 22:49:04+00	2026-02-18 22:49:04+00
4871	1771	76	1	f	t	0	Low dose to test response.	2026-02-18 22:49:33+00	2026-02-18 22:49:33+00
4872	1771	77	1	f	f	1	Medium dose for moderate effects.	2026-02-18 22:49:33+00	2026-02-18 22:49:33+00
4873	1771	78	1	f	f	2	High dose for heavy effect.	2026-02-18 22:49:33+00	2026-02-18 22:49:33+00
4874	1772	35	1	f	t	0	Low dose to test response.	2026-02-18 22:49:33+00	2026-02-18 22:49:33+00
4875	1772	30	1	f	f	1	Medium dose for moderate efficacy.	2026-02-18 22:49:33+00	2026-02-18 22:49:33+00
4876	1772	31	1	f	f	2	High dose for top-end effects.	2026-02-18 22:49:33+00	2026-02-18 22:49:33+00
4877	1773	148	13	f	t	0	Low dose for anti-aging, performance and well-being or maintenance.	2026-02-18 22:50:10+00	2026-02-18 22:50:10+00
4878	1773	152	13	f	f	1	Moderate dose for anti-aging, performance and well-being.	2026-02-18 22:50:10+00	2026-02-18 22:50:10+00
4879	1773	153	13	f	f	2	High dose for intense recovery and performance support.	2026-02-18 22:50:10+00	2026-02-18 22:50:10+00
4880	1774	154	1	f	t	0	Low dose for light cognitive support.	2026-02-18 22:50:10+00	2026-02-18 22:50:10+00
4881	1774	155	1	f	f	1	Moderate dose for Moderate cognitive support and neuroprotection.	2026-02-18 22:50:10+00	2026-02-18 22:50:10+00
4882	1774	53	9	f	f	2	High dose for intense cognitive enhancement and neuroprotection.	2026-02-18 22:50:10+00	2026-02-18 22:50:10+00
4883	1775	170	1	f	t	0	Low dose. Test response and titrate up if needed.	2026-02-18 22:50:44+00	2026-02-18 22:50:44+00
4884	1775	171	1	f	f	1	Moderate dose. Stimulating and memory enhancing.	2026-02-18 22:50:44+00	2026-02-18 22:50:44+00
4885	1775	172	1	f	f	2	High dose. Unrecommended to scale higher.	2026-02-18 22:50:44+00	2026-02-18 22:50:44+00
4886	1776	209	1	f	t	0	Low dose for anti-aging benefits or light social lubrication.	2026-02-18 22:51:11+00	2026-02-18 22:51:11+00
4887	1776	210	1	f	f	1	Standard moderate dose for anti-aging, social lubrication and muscular benefits.	2026-02-18 22:51:11+00	2026-02-18 22:51:11+00
4888	1777	209	1	f	t	0	Low dose for PTSD, Anxiety and Autism therapy or on-demand usage for mild social lubrication.	2026-02-18 22:51:11+00	2026-02-18 22:51:11+00
4889	1777	210	1	f	f	1	Moderate dose for PTSD, Autism and Anxiety therapy or intense on-demand social lubrication.	2026-02-18 22:51:11+00	2026-02-18 22:51:11+00
4890	1777	213	17	f	f	2	Optimal and Research-Standard dose for muscular hypertrophy and fatloss.	2026-02-18 22:51:11+00	2026-02-18 22:51:11+00
4891	1778	70	13	f	t	0	Thrice weekly injection due to long half-life. Low dosage to test response.	2026-02-18 22:51:39+00	2026-02-18 22:51:39+00
4892	1778	71	13	f	f	1	Thrice weekly injection due to long half-life. Clinical trials dosage.	2026-02-18 22:51:39+00	2026-02-18 22:51:39+00
4893	1778	72	13	f	f	2	Thrice weekly injection due to long half-life. High-end dosage.	2026-02-18 22:51:39+00	2026-02-18 22:51:39+00
4894	1779	128	1	f	t	0	Low dose. Increase if needed.	2026-02-18 22:52:05+00	2026-02-18 22:52:05+00
4895	1779	129	1	f	f	1	Moderate dose. Most commonly used.	2026-02-18 22:52:05+00	2026-02-18 22:52:05+00
4896	1779	192	1	f	f	2	High Dose. Maximum recommended dose.	2026-02-18 22:52:05+00	2026-02-18 22:52:05+00
4897	1780	38	1	t	t	0	Low dose to assess response. Use as needed before sexual activity.	2026-02-18 22:52:42+00	2026-02-18 22:52:42+00
4898	1780	39	1	f	f	1	Higher dose for individuals with severe dysfunction.	2026-02-18 22:52:42+00	2026-02-18 22:52:42+00
4899	1780	40	1	f	f	2	Highest recommended dose.	2026-02-18 22:52:42+00	2026-02-18 22:52:42+00
4900	1781	22	1	t	t	0	Low dose nasal spray as needed for convenience.	2026-02-18 22:52:42+00	2026-02-18 22:52:42+00
4901	1781	64	1	f	f	1	Moderate dose nasal spray as needed for convenience.	2026-02-18 22:52:42+00	2026-02-18 22:52:42+00
4902	1781	92	1	f	f	2	Maximum recommended nasal spray dose.	2026-02-18 22:52:42+00	2026-02-18 22:52:42+00
4903	1782	230	9	f	t	0	Standard concentration usually used for acne and hair loss.	2026-02-18 22:53:19+00	2026-02-18 22:53:19+00
4904	1782	231	9	f	f	1	High concentration used for severe cases.	2026-02-18 22:53:19+00	2026-02-18 22:53:19+00
4905	1783	63	1	t	t	0	Daily injection for anxiety relief	2026-02-18 22:53:50+00	2026-02-18 22:53:50+00
4906	1783	72	1	f	f	1	High dose daily injection for anxiety relief	2026-02-18 22:53:50+00	2026-02-18 22:53:50+00
4907	1784	63	11	t	t	0	Up to thrice daily nasal spray for anxiety and stress management	2026-02-18 22:53:50+00	2026-02-18 22:53:50+00
4908	1784	146	11	f	f	1	Higher nasal dose for severe anxiety. Up to thrice daily	2026-02-18 22:53:50+00	2026-02-18 22:53:50+00
4909	1785	120	9	f	t	0	Low dose for General cognitive enhancement.	2026-02-18 22:54:25+00	2026-02-18 22:54:25+00
4910	1785	63	11	f	f	1	Consistent regiment for improved memory and learning	2026-02-18 22:54:25+00	2026-02-18 22:54:25+00
4911	1785	146	11	f	f	2	Intense regiment for recovery or extreme enhancement.	2026-02-18 22:54:25+00	2026-02-18 22:54:25+00
4912	1786	35	13	f	t	0	Minimum Effective Dosage for a sparse frequency injection protocol. Mild Injury Prevention or Tissue Regeneration.	2026-02-18 22:54:56+00	2026-02-18 22:54:56+00
4913	1786	218	13	f	f	1	Most optimal version of sparse frequency injection protocol. Maintenance after injury rehab or injury prevention.	2026-02-18 22:54:56+00	2026-02-18 22:54:56+00
4914	1786	35	1	f	f	2	Daily injections of minimal dose. Very effective and preferable protocol, but harder to stick to.	2026-02-18 22:54:56+00	2026-02-18 22:54:56+00
4915	1786	216	1	f	f	3	Daily injections of moderate dose. Ideal for physically demanding circumstances.	2026-02-18 22:54:56+00	2026-02-18 22:54:56+00
4916	1786	157	1	f	f	4	Intense protocol. Daily injections of sub-maximal dosage for injury rehab,	2026-02-18 22:54:56+00	2026-02-18 22:54:56+00
4917	1786	217	1	f	f	5	Maximum Intensity protocol. Reserved for severe injury recovey	2026-02-18 22:54:56+00	2026-02-18 22:54:56+00
4918	1787	22	1	f	t	0	Budget Friendly dosing. Daily injection before bed for optimal GH release.\n\n	2026-02-18 22:55:46+00	2026-02-18 22:55:46+00
4919	1787	23	1	f	f	1	Optimal dosage. Daily injection before bed for optimal GH release.	2026-02-18 22:55:46+00	2026-02-18 22:55:46+00
4920	1788	136	9	f	t	0	Low dose. Safe and effective. Up to twice daily.	2026-02-18 22:56:14+00	2026-02-18 22:56:14+00
4921	1788	138	9	f	f	1	Moderate dose. Higher risk of hypotension or diarrhea, but stronger effects. Up to twice daily.	2026-02-18 22:56:14+00	2026-02-18 22:56:14+00
4922	1788	122	9	f	f	2	High dosage for experimentation. Up to twice daily.	2026-02-18 22:56:14+00	2026-02-18 22:56:14+00
4923	1789	99	1	f	t	0	Low dose. Safe and effective.	2026-02-18 22:56:14+00	2026-02-18 22:56:14+00
4924	1789	100	9	f	f	1	Moderate dose. Higher risk of hypotension or diarrhea, but stronger effects.	2026-02-18 22:56:14+00	2026-02-18 22:56:14+00
4925	1789	122	9	f	f	2	High dosage for experimentation.	2026-02-18 22:56:14+00	2026-02-18 22:56:14+00
\.


--
-- Data for Name: protocol_quality_indicators; Type: TABLE DATA; Schema: public; Owner: -
--

COPY public.protocol_quality_indicators (id, protocol_id, indicator_title, indicator_description, sort_order, created_at, updated_at) FROM stdin;
\.


--
-- Data for Name: research_studies; Type: TABLE DATA; Schema: public; Owner: -
--

COPY public.research_studies (id, title, authors, journal, publication_year, abstract, key_findings, url, tags, created_at, updated_at) FROM stdin;
\.


--
-- Data for Name: roles; Type: TABLE DATA; Schema: public; Owner: -
--

COPY public.roles (id, name, description, permissions, is_system_role, created_at, updated_at) FROM stdin;
1	user	Default role for calculator app users	{"calculator": ["read", "write", "delete"]}	t	2026-04-28 21:47:15.881+00	2026-04-28 21:47:15.881+00
2	influencer	Influencer with referral capabilities	{"coupons": ["read"], "analytics": ["read"], "referrals": ["create", "read"]}	f	2026-05-01 19:37:09.798+00	2026-05-01 19:37:09.798+00
\.


--
-- Data for Name: schedules; Type: TABLE DATA; Schema: public; Owner: -
--

COPY public.schedules (id, name, frequency, timing, duration, instructions, color_bg, color_text, icon, sort_order, is_active, deleted_at, created_at, updated_at) FROM stdin;
1	Daily	1x daily	Morning	4-8 weeks	Take consistently at the same time each day	#E3F2FD	#1565C0	Clock	1	t	\N	2025-07-15 17:14:31+00	2025-07-24 02:53:21+00
2	Twice Weekly	2x weekly	Mon/Thu evenings	8-12 weeks	Allow 72 hours between doses	#F3E5F5	#6A1B9A	Clock	2	t	\N	2025-07-15 17:14:31+00	2025-07-24 02:53:27+00
3	Cycling Protocol	5 days on, 2 days off	Morning	6 weeks	Cycle weekly to prevent tolerance	#FFF8E1	#F57F17	Clock	3	t	\N	2025-07-15 17:14:31+00	2025-07-24 02:53:32+00
7	Frequent Injections	3x Daily	Morning, Afternoon, Evening	3 months	Frequent Injections for stable blood levels	#E3F2FD	#1565C0	Clock	0	t	\N	2025-08-06 23:44:30+00	2025-08-06 23:44:30+00
8	4 weeks on, 2 weeks off Cycle	once daily	Morning	12 weeks	\N	#E3F2FD	#1565C0	Clock	0	t	\N	2025-08-07 20:20:43+00	2025-08-07 20:20:43+00
9	Twice Daily	2x daily	Morning, Evening	12 weeks	\N	#E3F2FD	#1565C0	Clock	0	t	\N	2025-08-07 20:27:44+00	2025-08-07 20:27:44+00
11	Thrice Daily	3x daily	Morning, Afternoon, Before Bed	8 weeks	\N	#E3F2FD	#1565C0	Clock	0	t	\N	2025-08-13 12:46:50+00	2025-08-13 12:46:50+00
12	Weekly	1x weekly	One specific day.	8-12 weeks	\N	#E3F2FD	#1565C0	Clock	0	t	\N	2025-08-19 23:40:07+00	2025-08-19 23:40:07+00
13	Thrice Weekly	3x weekly	Monday, Wednesday, Friday	8-12 weeks	\N	#E3F2FD	#1565C0	Clock	0	t	\N	2025-08-22 01:05:38+00	2025-08-22 01:05:38+00
14	2 week cycle	1x daily	Daily Morning	2 weeks on, 3+ months off	\N	#E3F2FD	#1565C0	Clock	0	t	\N	2025-08-30 13:27:58+00	2025-08-30 13:27:58+00
15	2 week cycle	3x daily	Morning, Afternoon and Evening	2 weeks	\N	#E3F2FD	#1565C0	Clock	0	t	\N	2025-08-30 13:34:49+00	2025-08-30 13:34:49+00
16	1 Week Cycle Twice a Year	1x daily	Morning	1 week	\N	#E3F2FD	#1565C0	Clock	0	t	\N	2025-11-01 04:41:15+00	2025-11-01 04:41:15+00
17	4 Times Daily	4x daily	Morning, Noon, Afternoon, Evening	8 weeks or as desired	\N	#E3F2FD	#1565C0	Clock	0	t	\N	2025-11-22 06:19:35+00	2025-11-22 06:19:35+00
\.


--
-- Data for Name: sds_analytics; Type: TABLE DATA; Schema: public; Owner: -
--

COPY public.sds_analytics (id, ip_address, action, compound_id, document_id, page_url, user_agent, "timestamp") FROM stdin;
\.


--
-- Data for Name: sds_batches; Type: TABLE DATA; Schema: public; Owner: -
--

COPY public.sds_batches (id, status, total, done, failed, user_email, company_profile, template_config, watermark_text, fields, cids, compound_statuses, document_ids, created_at, completed_at) FROM stdin;
\.


--
-- Data for Name: sds_compounds; Type: TABLE DATA; Schema: public; Owner: -
--

COPY public.sds_compounds (id, peptide_id, name, cas_number, pubchem_cid, iupac_name, molecular_formula, molecular_weight, synonyms, smiles, inchi_key, inchi, appearance, odor, boiling_point, melting_point, flash_point, vapor_pressure, vapor_density, specific_gravity, solubility, ph, fetch_status, last_fetched_at, created_at, deleted_at) FROM stdin;
bda46d0b-3add-4d33-8f00-138a7503628e	\N	Semaglutide	910463-68-2	56843331	\N	\N	\N	\N	\N	\N	\N	\N	\N	\N	\N	\N	\N	\N	\N	\N	\N	pending	2026-04-23 01:39:38.224978+00	2026-04-23 01:39:38.224978+00	\N
ca094e09-03ad-407d-a318-b56cbb54aa14	\N	Tirzepatide	2381089-83-2	168009818	\N	\N	\N	\N	\N	\N	\N	\N	\N	\N	\N	\N	\N	\N	\N	\N	\N	pending	2026-04-23 01:39:38.224978+00	2026-04-23 01:39:38.224978+00	\N
d1870fd9-8d0e-47c2-9db3-7d21866c55f7	\N	Liraglutide	204656-20-2	16134956	\N	\N	\N	\N	\N	\N	\N	\N	\N	\N	\N	\N	\N	\N	\N	\N	\N	pending	2026-04-23 01:39:38.224978+00	2026-04-23 01:39:38.224978+00	\N
92013219-c198-4275-8596-59ca5892aa00	\N	Exenatide	141758-74-9	45588096	\N	\N	\N	\N	\N	\N	\N	\N	\N	\N	\N	\N	\N	\N	\N	\N	\N	pending	2026-04-23 01:39:38.224978+00	2026-04-23 01:39:38.224978+00	\N
35479c4d-b9b5-4985-93b4-b17fd1f611bf	\N	Albiglutide	782500-75-8	122173812	\N	\N	\N	\N	\N	\N	\N	\N	\N	\N	\N	\N	\N	\N	\N	\N	\N	pending	2026-04-23 01:39:38.224978+00	2026-04-23 01:39:38.224978+00	\N
d9e6143a-a010-422c-8bda-7c73aea9234b	\N	Sermorelin	86168-78-7	16132413	\N	\N	\N	\N	\N	\N	\N	\N	\N	\N	\N	\N	\N	\N	\N	\N	\N	pending	2026-04-23 01:39:38.224978+00	2026-04-23 01:39:38.224978+00	\N
897c9575-34c0-485a-b75d-7691c1661904	\N	Ipamorelin	170851-70-4	9831659	\N	\N	\N	\N	\N	\N	\N	\N	\N	\N	\N	\N	\N	\N	\N	\N	\N	pending	2026-04-23 01:39:38.224978+00	2026-04-23 01:39:38.224978+00	\N
b524e7e0-57d3-41bc-afff-e0d5ca822a57	\N	GHRP-2	158861-67-7	6918245	\N	\N	\N	\N	\N	\N	\N	\N	\N	\N	\N	\N	\N	\N	\N	\N	\N	pending	2026-04-23 01:39:38.224978+00	2026-04-23 01:39:38.224978+00	\N
d4ccb780-b2a7-4b1a-a688-b5c1df41ea0c	\N	AOD-9604	221231-10-3	71300630	\N	\N	\N	\N	\N	\N	\N	\N	\N	\N	\N	\N	\N	\N	\N	\N	\N	pending	2026-04-23 01:39:38.224978+00	2026-04-23 01:39:38.224978+00	\N
4e8a6733-4252-43ab-893d-8cab880a4b59	\N	Hexarelin	140703-51-1	6918297	\N	\N	\N	\N	\N	\N	\N	\N	\N	\N	\N	\N	\N	\N	\N	\N	\N	pending	2026-04-23 01:39:38.224978+00	2026-04-23 01:39:38.224978+00	\N
ab61431c-3db1-471b-9a01-77906738fa95	\N	Tesamorelin	218949-48-5	16137828	\N	\N	\N	\N	\N	\N	\N	\N	\N	\N	\N	\N	\N	\N	\N	\N	\N	pending	2026-04-23 01:39:38.224978+00	2026-04-23 01:39:38.224978+00	\N
3bcd2765-0ba7-46ae-ad6a-774ca71511f7	\N	CJC-1295	863288-34-0	91971820	\N	\N	\N	\N	\N	\N	\N	\N	\N	\N	\N	\N	\N	\N	\N	\N	\N	pending	2026-04-23 01:39:38.224978+00	2026-04-23 01:39:38.224978+00	\N
47773c44-2a40-401a-9a07-831eef38f11b	\N	Ibutamoren (MK-677)	159634-47-6	178024	\N	\N	\N	\N	\N	\N	\N	\N	\N	\N	\N	\N	\N	\N	\N	\N	\N	pending	2026-04-23 01:39:38.224978+00	2026-04-23 01:39:38.224978+00	\N
d9cd71e1-88c3-4fdc-a69a-361ecc4a587e	\N	BPC-157	137525-51-0	9941957	\N	\N	\N	\N	\N	\N	\N	\N	\N	\N	\N	\N	\N	\N	\N	\N	\N	pending	2026-04-23 01:39:38.224978+00	2026-04-23 01:39:38.224978+00	\N
9b0a076e-3eae-47e0-9e60-afb9697b62bd	\N	Epithalon	307297-39-8	219042	\N	\N	\N	\N	\N	\N	\N	\N	\N	\N	\N	\N	\N	\N	\N	\N	\N	pending	2026-04-23 01:39:38.224978+00	2026-04-23 01:39:38.224978+00	\N
dd4cee8a-8f18-42ef-9583-1f878cabb434	\N	Selank	129954-34-3	11765600	\N	\N	\N	\N	\N	\N	\N	\N	\N	\N	\N	\N	\N	\N	\N	\N	\N	pending	2026-04-23 01:39:38.224978+00	2026-04-23 01:39:38.224978+00	\N
3d989565-15fc-4c97-b36d-809d38491586	\N	Semax	80714-61-0	9811102	\N	\N	\N	\N	\N	\N	\N	\N	\N	\N	\N	\N	\N	\N	\N	\N	\N	pending	2026-04-23 01:39:38.224978+00	2026-04-23 01:39:38.224978+00	\N
0c9c4f54-22e1-4ac2-bde4-e36fba82c5df	\N	DSIP	62568-57-4	68816	\N	\N	\N	\N	\N	\N	\N	\N	\N	\N	\N	\N	\N	\N	\N	\N	\N	pending	2026-04-23 01:39:38.224978+00	2026-04-23 01:39:38.224978+00	\N
5d1904b9-e78d-4b21-aa85-5f506dbf0ce1	\N	Dihexa	1401708-83-5	129010512	\N	\N	\N	\N	\N	\N	\N	\N	\N	\N	\N	\N	\N	\N	\N	\N	\N	pending	2026-04-23 01:39:38.224978+00	2026-04-23 01:39:38.224978+00	\N
21c7c9f0-6b64-43c8-a840-743acd812cb7	\N	Thymosin Alpha-1	62304-98-7	16130571	\N	\N	\N	\N	\N	\N	\N	\N	\N	\N	\N	\N	\N	\N	\N	\N	\N	pending	2026-04-23 01:39:38.224978+00	2026-04-23 01:39:38.224978+00	\N
4855e9da-6071-43fa-8d79-dca409ee84bc	\N	Thymosin Beta-4	77591-33-4	45382195	\N	\N	\N	\N	\N	\N	\N	\N	\N	\N	\N	\N	\N	\N	\N	\N	\N	pending	2026-04-23 01:39:38.224978+00	2026-04-23 01:39:38.224978+00	\N
74a5ffab-9a65-4ae3-9b6f-66dd2414e984	\N	Elamipretide	736992-21-5	11764719	\N	\N	\N	\N	\N	\N	\N	\N	\N	\N	\N	\N	\N	\N	\N	\N	\N	pending	2026-04-23 01:39:38.224978+00	2026-04-23 01:39:38.224978+00	\N
4836f448-8220-49b5-b46b-54754705fbc1	\N	GHK-Cu	49557-75-7	9831891	\N	\N	\N	\N	\N	\N	\N	\N	\N	\N	\N	\N	\N	\N	\N	\N	\N	pending	2026-04-23 01:39:38.224978+00	2026-04-23 01:39:38.224978+00	\N
b2e9e612-84ad-4da7-af88-36e006f0bd98	\N	Somatostatin	38916-34-6	16129706	\N	\N	\N	\N	\N	\N	\N	\N	\N	\N	\N	\N	\N	\N	\N	\N	\N	pending	2026-04-23 01:39:38.224978+00	2026-04-23 01:39:38.224978+00	\N
c7bacacf-6a4c-45a5-b00f-10feafeabdf4	\N	Substance P	33507-63-0	36511	\N	\N	\N	\N	\N	\N	\N	\N	\N	\N	\N	\N	\N	\N	\N	\N	\N	pending	2026-04-23 01:39:38.224978+00	2026-04-23 01:39:38.224978+00	\N
98e06c99-c8f2-4412-8613-84186938c283	\N	Melanotan II	121062-08-6	92432	\N	\N	\N	\N	\N	\N	\N	\N	\N	\N	\N	\N	\N	\N	\N	\N	\N	pending	2026-04-23 01:39:38.224978+00	2026-04-23 01:39:38.224978+00	\N
7b5d6fae-29d1-4f5a-ad73-45d9c80e3b51	\N	Bremelanotide	189691-06-3	9941379	\N	\N	\N	\N	\N	\N	\N	\N	\N	\N	\N	\N	\N	\N	\N	\N	\N	pending	2026-04-23 01:39:38.224978+00	2026-04-23 01:39:38.224978+00	\N
b930d03c-144e-4d94-870b-edbec85fe185	\N	Setmelanotide	920014-72-8	11993702	\N	\N	\N	\N	\N	\N	\N	\N	\N	\N	\N	\N	\N	\N	\N	\N	\N	pending	2026-04-23 01:39:38.224978+00	2026-04-23 01:39:38.224978+00	\N
24dfdba4-804a-4ec6-a07a-09ab1d4a2754	\N	Gonadorelin	33515-09-2	638793	\N	\N	\N	\N	\N	\N	\N	\N	\N	\N	\N	\N	\N	\N	\N	\N	\N	pending	2026-04-23 01:39:38.224978+00	2026-04-23 01:39:38.224978+00	\N
0d496904-5af9-49b4-b5b9-965e5771f415	\N	Leuprolide	53714-56-0	657181	\N	\N	\N	\N	\N	\N	\N	\N	\N	\N	\N	\N	\N	\N	\N	\N	\N	pending	2026-04-23 01:39:38.224978+00	2026-04-23 01:39:38.224978+00	\N
e090299a-fc4e-44af-926e-023990b3f1dd	\N	Triptorelin	57773-63-4	25074470	\N	\N	\N	\N	\N	\N	\N	\N	\N	\N	\N	\N	\N	\N	\N	\N	\N	pending	2026-04-23 01:39:38.224978+00	2026-04-23 01:39:38.224978+00	\N
8641f300-b0d6-49eb-a748-a8f7259d4d71	\N	Buserelin	57982-77-1	50225	\N	\N	\N	\N	\N	\N	\N	\N	\N	\N	\N	\N	\N	\N	\N	\N	\N	pending	2026-04-23 01:39:38.224978+00	2026-04-23 01:39:38.224978+00	\N
ab2145ba-4ab2-4d3f-a8cc-597530e5d16f	\N	Nafarelin	76932-56-4	25077405	\N	\N	\N	\N	\N	\N	\N	\N	\N	\N	\N	\N	\N	\N	\N	\N	\N	pending	2026-04-23 01:39:38.224978+00	2026-04-23 01:39:38.224978+00	\N
d517270b-8337-4fae-8de5-320d6314d72a	\N	Histrelin	76712-82-8	25077993	\N	\N	\N	\N	\N	\N	\N	\N	\N	\N	\N	\N	\N	\N	\N	\N	\N	pending	2026-04-23 01:39:38.224978+00	2026-04-23 01:39:38.224978+00	\N
d6927c4f-4b48-4982-9b64-e8eef8c5a257	\N	Degarelix	214766-78-6	16136245	\N	\N	\N	\N	\N	\N	\N	\N	\N	\N	\N	\N	\N	\N	\N	\N	\N	pending	2026-04-23 01:39:38.224978+00	2026-04-23 01:39:38.224978+00	\N
6744ebde-4b20-4ff3-a805-bf4a0a7cadf6	\N	Cetrorelix	120287-85-6	25074887	\N	\N	\N	\N	\N	\N	\N	\N	\N	\N	\N	\N	\N	\N	\N	\N	\N	pending	2026-04-23 01:39:38.224978+00	2026-04-23 01:39:38.224978+00	\N
7577cf9d-03c1-4ad5-9271-881db956ec6d	\N	Glucagon	16941-32-5	16132283	\N	\N	\N	\N	\N	\N	\N	\N	\N	\N	\N	\N	\N	\N	\N	\N	\N	pending	2026-04-23 01:39:38.224978+00	2026-04-23 01:39:38.224978+00	\N
2b4eddc5-5dae-4167-8f57-84f27a94a123	\N	Oxytocin	50-56-6	439302	\N	\N	\N	\N	\N	\N	\N	\N	\N	\N	\N	\N	\N	\N	\N	\N	\N	pending	2026-04-23 01:39:38.224978+00	2026-04-23 01:39:38.224978+00	\N
3601c714-ebfd-468b-bdb1-f1bdb58be945	\N	Vasopressin	11000-17-2	644077	\N	\N	\N	\N	\N	\N	\N	\N	\N	\N	\N	\N	\N	\N	\N	\N	\N	pending	2026-04-23 01:39:38.224978+00	2026-04-23 01:39:38.224978+00	\N
57cea345-978f-4b5e-a469-d82da924f66e	\N	Desmopressin	16679-58-6	5311065	\N	\N	\N	\N	\N	\N	\N	\N	\N	\N	\N	\N	\N	\N	\N	\N	\N	pending	2026-04-23 01:39:38.224978+00	2026-04-23 01:39:38.224978+00	\N
16e5b7b1-80d0-4247-827e-5917479c912a	\N	Calcitonin (Salmon)	47931-85-1	16220016	\N	\N	\N	\N	\N	\N	\N	\N	\N	\N	\N	\N	\N	\N	\N	\N	\N	pending	2026-04-23 01:39:38.224978+00	2026-04-23 01:39:38.224978+00	\N
b5f6a98e-515b-4bfe-9b72-e975aa3ab234	\N	Kisspeptin-10	374675-21-5	25240297	\N	\N	\N	\N	\N	\N	\N	\N	\N	\N	\N	\N	\N	\N	\N	\N	\N	pending	2026-04-23 01:39:38.224978+00	2026-04-23 01:39:38.224978+00	\N
766a28b7-34d0-4074-b7c0-6c7ca50b751f	\N	Pramlintide	151126-32-8	70691388	\N	\N	\N	\N	\N	\N	\N	\N	\N	\N	\N	\N	\N	\N	\N	\N	\N	pending	2026-04-23 01:39:38.224978+00	2026-04-23 01:39:38.224978+00	\N
d8cd4d62-aa2e-49ad-a1ea-68eb3dde405b	\N	Thymulin	63958-90-7	71300623	\N	\N	\N	\N	\N	\N	\N	\N	\N	\N	\N	\N	\N	\N	\N	\N	\N	pending	2026-04-23 01:39:38.224978+00	2026-04-23 01:39:38.224978+00	\N
9d3663e1-7fe3-4fb3-9d1e-555c0b3cd458	\N	LL-37	2762-77-8	16198951	\N	\N	\N	\N	\N	\N	\N	\N	\N	\N	\N	\N	\N	\N	\N	\N	\N	pending	2026-04-23 01:39:38.224978+00	2026-04-23 01:39:38.224978+00	\N
f9aa33ba-221e-4678-8f4b-0f56306d1da6	\N	Humanin	330936-69-1	16131438	\N	\N	\N	\N	\N	\N	\N	\N	\N	\N	\N	\N	\N	\N	\N	\N	\N	pending	2026-04-23 01:39:38.224978+00	2026-04-23 01:39:38.224978+00	\N
aed55dc7-bb86-41cd-9481-ecfae9a8027a	\N	Eptifibatide	148031-34-9	448812	\N	\N	\N	\N	\N	\N	\N	\N	\N	\N	\N	\N	\N	\N	\N	\N	\N	pending	2026-04-23 01:39:38.224978+00	2026-04-23 01:39:38.224978+00	\N
008cf3b2-83bc-4e62-aa3e-69ffa21f70ef	\N	Afamelanotide	75921-69-6	16197727	(4S)-4-[[(2S)-2-[[(2S)-2-[[(2S)-2-[[(2S)-2-acetamido-3-hydroxypropanoyl]amino]-3-(4-hydroxyphenyl)propanoyl]amino]-3-hydroxypropanoyl]amino]hexanoyl]amino]-5-[[(2S)-1-[[(2R)-1-[[(2S)-1-[[(2S)-1-[[2-[[(2S)-6-amino-1-[(2S)-2-[[(2S)-1-amino-3-methyl-1-oxobutan-2-yl]carbamoyl]pyrrolidin-1-yl]-1-oxohexan-2-yl]amino]-2-oxoethyl]amino]-3-(1H-indol-3-yl)-1-oxopropan-2-yl]amino]-5-carbamimidamido-1-oxopentan-2-yl]amino]-1-oxo-3-phenylpropan-2-yl]amino]-3-(1H-imidazol-5-yl)-1-oxopropan-2-yl]amino]-5-oxopentanoic acid	C78H111N21O19	1646.8	{Afamelanotide,Melanotan,4-Norleucyl-7-phenylalanine-alpha-msh,DTXSID40226843,NDPMSH,"(Nle(4),D-Phe(7))alpha-MSH",RefChem:57383,D02BB02,DTXCID70149334,"(4S)-4-(((2S)-2-(((2S)-2-(((2S)-2-(((2S)-2-acetamido-3-hydroxypropanoyl)amino)-3-(4-hydroxyphenyl)propanoyl)amino)-3-hydroxypropanoyl)amino)hexanoyl)amino)-5-(((2S)-1-(((2R)-1-(((2S)-1-(((2S)-1-((2-(((2S)-6-amino-1-((2S)-2-(((2S)-1-amino-3-methyl-1-oxobutan-2-yl)carbamoyl)pyrrolidin-1-yl)-1-oxohexan-2-yl)amino)-2-oxoethyl)amino)-3-(1H-indol-3-yl)-1-oxopropan-2-yl)amino)-5-carbamimidamido-1-oxopentan-2-yl)amino)-1-oxo-3-phenylpropan-2-yl)amino)-3-(1H-imidazol-4-yl)-1-oxopropan-2-yl)amino)-5-oxopentanoic acid",4-Nle-7-Phe-alpha-MSH,75921-69-6,Ac-Ser-Tyr-Ser-Nle-Glu-His-D-Phe-Arg-Trp-Gly-Lys-Pro-Val-NH2,afamelanotida,afamelanotidum,"alpha-MSH, Nle(4)-Phe(7)-","alpha-MSH, norleucyl(4)-D-phenylalanyl(7)-",CHEBI:136034,"CUV 1647",CUV-1647,CUV1647,"Melanotan I",Melanotan-1,"MSH, 4-Nle-7-Phe-alpha-","Msh, 4-norleucyl-7-phenylalanine-alpha-","MT-1 (NleFMSH)",NDP-alpha-MSH,Ndp-msh,QW68W3J66U,alpha-NDP-MSH,"[Nle4,dPhe7]alpha-MSH",Afamelanotide?,"Scenesse (TN)","Afamelanotide (USAN/INN)",GTPL1324,SCHEMBL28803668,BDBM50017181,AKOS040763896,DB04931,NCGC00167334-01,DA-50255,D10511,Q410794}	\N	UAHFGYDRQSXQEB-LEBBXHLNSA-N	\N	\N	\N	\N	\N	\N	\N	\N	\N	\N	\N	complete	2026-04-25 01:16:21.39+00	2026-04-23 01:39:38.224978+00	\N
2db3733b-2f29-4277-9471-6702235ed1a3	\N	methylene blue	61-73-4	6099	[7-(dimethylamino)phenothiazin-3-ylidene]-dimethylazanium chloride	C16H18ClN3S	319.9	{"methylene blue",61-73-4,"Basic blue 9","Methylthioninium chloride","Solvent blue 8","Swiss Blue","Methylene Blue anhydrous",Chromosmon,"C.I. Basic Blue 9","Methylene Blue N","Methylthionine chloride","Methylene Blue BB","Methylene Blue chloride","Methylenium ceruleum","Urolene blue","Bleu de methylene","Methylene Blue A","Methylene Blue B","Methylene Blue D","Methylene Blue G","External Blue 1","Tetramethylene Blue","Calcozine Blue ZF","Methylene Blue BD","Methylene Blue BP","Methylene Blue BX","Methylene Blue BZ","Methylene Blue FZ","Methylene Blue GZ","Methylene Blue NZ","Methylene Blue SG","Methylene Blue SP","Methylene Blue ZF","Methylene Blue ZX",Methylenblau,"Methylene Blue 2B","Methylene Blue BBA","Methylene Blue BPC","Methylene Blue HGG","Methylene Blue IAD","Methylene Blue JFA","Sandocryl Blue BRL","Methylene Blue 2BF","Methylene Blue 2BN","Methylene Blue 2BP","Modr methylenova","Mitsui Methylene Blue","Tetramethylthionine chloride","Methylthionium chloride","Leather Pure Blue HB"}	CN(C)c1ccc2nc3ccc(N(C)C)cc3[s+]c2c1.[Cl-]	CXKWCBBOMKCUKX-UHFFFAOYSA-M	\N	Dark green crystalline powder with bronze-like luster, forming a deep blue solution in water	Odorless	\N	100 to 110 °C (with decomposition) 100-110 °C (decomposes)	\N	0.00000013 [mmHg]	\N	\N	Soluble in water (approximately 40 g/L at 20°C); soluble in ethanol and chloroform; slightly soluble in pyridine	3.0-4.5 (10 g/L aqueous solution)	complete	2026-05-05 14:24:39.848+00	2026-05-05 14:24:39.871995+00	\N
\.


--
-- Data for Name: sds_documents; Type: TABLE DATA; Schema: public; Owner: -
--

COPY public.sds_documents (id, compound_id, company_name, company_address, company_phone, company_emergency_contact, company_emergency_phone, company_logo_url, company_website, pdf_url, version, revision_date, manual_overrides, watermark_text, generated_at, deleted_at, user_id) FROM stdin;
1a2ed34d-8eb5-4029-bf0a-5e882e56746a	2db3733b-2f29-4277-9471-6702235ed1a3	Carlos LLC	US	1233445667	CHEMTREC	800-424-9300 CHEMTREC (USA) +1-703-527-3887 CHEMTREC (International) 24 Hours/day; 7 Days/week	\N	\N	https://iwkgpdisgmvvfkielgop.supabase.co/storage/v1/object/public/sds-pdfs/1a2ed34d-8eb5-4029-bf0a-5e882e56746a.pdf	1	2026-05-05	{"odor": "Odorless", "appearance": "Dark green crystalline powder with bronze-like luster, forming a deep blue solution in water", "signalWord": "Danger", "solubility": "Soluble in water (approximately 40 g/L at 20°C); soluble in ethanol and chloroform; slightly soluble in pyridine", "ecotoxicity": "LC50; Species: Penaeus californiensis (Shrimp) age 6 months, weight 2.54 g; Conditions: saltwater, static, 27 °C, salinity 24 ppt; Concentration: 100,000 ug/L for 1 hr LC50; Species: Heteropneustes fossilis (Indian catfish) adult, weight 22.2 g, length 18.3 cm; Conditions: freshwater, renewal, 18-22 °C; Concentration: 188500 ug/L for 24 hr (95% confidence interval: 184260-192840 ug/L) /formulated product/ LC50; Species: Heteropneustes fossilis (Indian catfish) adult, weight 22.2 g, length 18.3 c", "persistence": "ANAEROBIC: The objective of this study is to evaluate the decolorization of Methylene Blue (MB) by an up-flow anaerobic sludge blanket (UASB) reactor. The UASB reactor was operated under batch condition with total treatment volume of 3 L and operation time of 24 hrs per batch. It was found that the color of MB disappeared within a few minutes after entering into the UASB reactor due to reduction b", "meltingPoint": "100 to 110 °C (with decomposition) 100-110 °C (decomposes)", "vaporPressure": "0.00000013 [mmHg]", "identifiedUses": "Research laboratory chemical for in vitro scientific research and development use only.", "ppeRespiratory": "Eye/face protection: Use equipment for eye protection tested and approved under appropriate government standards such as NIOSH (US) or EN 166(EU). Skin protection: Handle with gloves. Body Protection: Impervious clothing. The type of protective equipment must be selected according to the concentrati", "bioaccumulation": "An estimated BCF of 3 was calculated in fish for methylene blue(SRC), using an estimated log Kow of 0.75(1) and a regression-derived equation(1). According to a classification scheme(2), this BCF suggests the potential for bioconcentration in aquatic organisms is low(SRC). The aquatic plant, Hydrilla verticillata was shown to remove methylene blue from aqueous solution rapidly; 100, 500, and 1000", "carcinogenicity": "Evaluation: No data were available to the Working Group for humans. There is limited evidence for the carcinogenicity of methylene blue in experimental animals. Overall evaluation: Methylene blue is not classifiable as to its carcinogenicity in humans (Group 3).", "hazardStatements": ["H302: Harmful if swallowed [Warning Acute toxicity, oral]", "H318: Causes serious eye damage [Danger Serious eye damage/eye irritation]", "H412: Harmful to aquatic life with long lasting effects [Hazardous to the aquatic environment, long-term hazard]", "H361: Suspected of damaging fertility or the unborn child [Warning Reproductive toxicity]", "H370: Causes damage to organs [Danger Specific target organ toxicity, single exposure]", "H372: Causes damage to organs through prolonged or repeated exposure [Danger Specific target organ toxicity, repeated exposure]"], "restrictionOnUse": "Not for human or veterinary use. Not for food, drug, cosmetic, household, agricultural, clinical, therapeutic, or diagnostic applications.", "storageConditions": "Keep container tightly closed in a dry and well-ventilated place. Storage class (TRGS 510): 11 - Combustible Solids. Commercially available methylene blue 10-mg/mL solution for IV use should be stored at 20-25 °C, but may be exposed to temperatures ranging from 15-30 °C.", "precautionaryStatements": ["P264", "P264+P265", "P270", "P273", "P280", "P301+P317", "P305+P354+P338", "P317", "P330", "P501", "P203", "P260", "P308+P316", "P318", "P319", "P321", "P405"]}	PEPSDS.AI	2026-05-05 14:25:15.953+00	\N	\N
\.


--
-- Data for Name: sds_hazard_data; Type: TABLE DATA; Schema: public; Owner: -
--

COPY public.sds_hazard_data (id, compound_id, signal_word, ghs_pictograms, hazard_statements, precautionary_statements, health_hazard, flammability, reactivity, specific_hazards, source, created_at, updated_at, deleted_at) FROM stdin;
a5a78881-e45e-43a0-a36e-8267602a6d3f	008cf3b2-83bc-4e62-aa3e-69ffa21f70ef	\N	\N	\N	\N	\N	\N	\N	\N	pubchem	2026-04-25 01:16:21.451741+00	2026-04-25 01:16:21.39+00	\N
fa50245c-346b-4750-a5ab-3ecebccf3202	2db3733b-2f29-4277-9471-6702235ed1a3	Danger	{GHS05,GHS07,GHS08}	{"H302: Harmful if swallowed [Warning Acute toxicity, oral]","H318: Causes serious eye damage [Danger Serious eye damage/eye irritation]","H412: Harmful to aquatic life with long lasting effects [Hazardous to the aquatic environment, long-term hazard]","H361: Suspected of damaging fertility or the unborn child [Warning Reproductive toxicity]","H370: Causes damage to organs [Danger Specific target organ toxicity, single exposure]","H372: Causes damage to organs through prolonged or repeated exposure [Danger Specific target organ toxicity, repeated exposure]"}	{P264,P264+P265,P270,P273,P280,P301+P317,P305+P354+P338,P317,P330,P501,P203,P260,P308+P316,P318,P319,P321,P405}	\N	\N	\N	\N	pubchem	2026-05-05 14:24:39.996143+00	2026-05-05 14:24:39.848+00	\N
\.


--
-- Data for Name: sds_job_queue; Type: TABLE DATA; Schema: public; Owner: -
--

COPY public.sds_job_queue (id, compound_id, type, status, priority, payload, result, error, attempts, max_attempts, created_at, updated_at, started_at, completed_at, user_id) FROM stdin;
\.


--
-- Data for Name: sds_pdf_templates; Type: TABLE DATA; Schema: public; Owner: -
--

COPY public.sds_pdf_templates (id, name, is_default, config, created_at, updated_at, deleted_at) FROM stdin;
\.


--
-- Data for Name: sds_pinned_compounds; Type: TABLE DATA; Schema: public; Owner: -
--

COPY public.sds_pinned_compounds (id, compound_id, display_name, pubchem_cid, drugbank_id, chembl_id, cas_number, molecular_formula, category, verified, sort_order, created_at, deleted_at) FROM stdin;
6ad4f2a3-d215-4cfa-9601-7d3255e8b6dd	bda46d0b-3add-4d33-8f00-138a7503628e	Semaglutide	56843331	\N	\N	910463-68-2	\N	GLP-1	t	1	2026-04-23 01:39:38.224978+00	\N
5593b1b6-189f-4026-8081-ebf935299b88	ca094e09-03ad-407d-a318-b56cbb54aa14	Tirzepatide	168009818	\N	\N	2381089-83-2	\N	GLP-1	t	2	2026-04-23 01:39:38.224978+00	\N
f1f396ff-8639-49b0-bc38-a0679e0959d1	d1870fd9-8d0e-47c2-9db3-7d21866c55f7	Liraglutide	16134956	\N	\N	204656-20-2	\N	GLP-1	t	3	2026-04-23 01:39:38.224978+00	\N
0d16fe47-68a6-4a5e-b673-b9994b9206e8	92013219-c198-4275-8596-59ca5892aa00	Exenatide	45588096	\N	\N	141758-74-9	\N	GLP-1	t	4	2026-04-23 01:39:38.224978+00	\N
a4e89226-f935-4162-890e-6de5945f6de3	35479c4d-b9b5-4985-93b4-b17fd1f611bf	Albiglutide	122173812	\N	\N	782500-75-8	\N	GLP-1	t	5	2026-04-23 01:39:38.224978+00	\N
4c1f693d-b6e7-437e-b172-0cfc7fcaa6bb	d9e6143a-a010-422c-8bda-7c73aea9234b	Sermorelin	16132413	\N	\N	86168-78-7	\N	Growth	t	6	2026-04-23 01:39:38.224978+00	\N
ddbc893f-bcce-4940-a965-6aa0ee4803da	897c9575-34c0-485a-b75d-7691c1661904	Ipamorelin	9831659	\N	\N	170851-70-4	\N	Growth	t	7	2026-04-23 01:39:38.224978+00	\N
594cac8d-63bb-4227-9bc2-f9f91e9a81eb	b524e7e0-57d3-41bc-afff-e0d5ca822a57	GHRP-2	6918245	\N	\N	158861-67-7	\N	Growth	t	8	2026-04-23 01:39:38.224978+00	\N
2c39440b-cd21-4acf-90b0-4c01643891ae	d4ccb780-b2a7-4b1a-a688-b5c1df41ea0c	AOD-9604	71300630	\N	\N	221231-10-3	\N	Growth	t	9	2026-04-23 01:39:38.224978+00	\N
1eecb671-1000-442c-a469-6b09772ce67c	4e8a6733-4252-43ab-893d-8cab880a4b59	Hexarelin	6918297	\N	\N	140703-51-1	\N	Growth	t	10	2026-04-23 01:39:38.224978+00	\N
ec8f8cee-95f9-4e1a-8b1c-3eb490f7a997	ab61431c-3db1-471b-9a01-77906738fa95	Tesamorelin	16137828	\N	\N	218949-48-5	\N	Growth	t	11	2026-04-23 01:39:38.224978+00	\N
69c12f51-e632-463f-9d6b-f59f05f54ef0	3bcd2765-0ba7-46ae-ad6a-774ca71511f7	CJC-1295	91971820	\N	\N	863288-34-0	\N	Growth	t	12	2026-04-23 01:39:38.224978+00	\N
7b928026-dfc5-4452-a9b0-11542a1f69e5	47773c44-2a40-401a-9a07-831eef38f11b	Ibutamoren (MK-677)	178024	\N	\N	159634-47-6	\N	Growth	t	13	2026-04-23 01:39:38.224978+00	\N
1f37d52c-1454-42cb-be96-8d709369611d	d9cd71e1-88c3-4fdc-a69a-361ecc4a587e	BPC-157	9941957	\N	\N	137525-51-0	\N	Research	t	14	2026-04-23 01:39:38.224978+00	\N
6ec7171c-68a0-4c0c-a045-e5ca036fd4cf	9b0a076e-3eae-47e0-9e60-afb9697b62bd	Epithalon	219042	\N	\N	307297-39-8	\N	Research	t	15	2026-04-23 01:39:38.224978+00	\N
eb42403d-741a-4ab2-a49b-72ae83f419fa	dd4cee8a-8f18-42ef-9583-1f878cabb434	Selank	11765600	\N	\N	129954-34-3	\N	Research	t	16	2026-04-23 01:39:38.224978+00	\N
c5323441-0ef3-4788-8107-22a0d336e5ac	3d989565-15fc-4c97-b36d-809d38491586	Semax	9811102	\N	\N	80714-61-0	\N	Research	t	17	2026-04-23 01:39:38.224978+00	\N
bc72ee49-cc08-41ab-aa41-ce07429fc4c9	0c9c4f54-22e1-4ac2-bde4-e36fba82c5df	DSIP	68816	\N	\N	62568-57-4	\N	Research	t	18	2026-04-23 01:39:38.224978+00	\N
528d3c14-642f-46c3-b5df-0eca9885c0d1	5d1904b9-e78d-4b21-aa85-5f506dbf0ce1	Dihexa	129010512	\N	\N	1401708-83-5	\N	Research	t	19	2026-04-23 01:39:38.224978+00	\N
7ac039e6-e5eb-4272-b744-115b507bcaa1	21c7c9f0-6b64-43c8-a840-743acd812cb7	Thymosin Alpha-1	16130571	\N	\N	62304-98-7	\N	Research	t	20	2026-04-23 01:39:38.224978+00	\N
2b5063c6-dbdc-4997-93dc-f04176015db8	4855e9da-6071-43fa-8d79-dca409ee84bc	Thymosin Beta-4	45382195	\N	\N	77591-33-4	\N	Research	t	21	2026-04-23 01:39:38.224978+00	\N
42dbe6f9-826b-4b56-adc4-08cf5e075f01	74a5ffab-9a65-4ae3-9b6f-66dd2414e984	Elamipretide	11764719	\N	\N	736992-21-5	\N	Research	t	22	2026-04-23 01:39:38.224978+00	\N
bd78523d-4609-4f4f-a7ac-c0609a5cacc7	4836f448-8220-49b5-b46b-54754705fbc1	GHK-Cu	9831891	\N	\N	49557-75-7	\N	Research	t	23	2026-04-23 01:39:38.224978+00	\N
82dfffd0-34e4-4f8b-a58f-e38b505825b7	b2e9e612-84ad-4da7-af88-36e006f0bd98	Somatostatin	16129706	\N	\N	38916-34-6	\N	Research	t	24	2026-04-23 01:39:38.224978+00	\N
789616d8-26ee-4df2-85de-f8cb14045cbe	c7bacacf-6a4c-45a5-b00f-10feafeabdf4	Substance P	36511	\N	\N	33507-63-0	\N	Research	t	25	2026-04-23 01:39:38.224978+00	\N
9a219179-a9cb-4f8a-83bd-47aaf6e2d519	98e06c99-c8f2-4412-8613-84186938c283	Melanotan II	92432	\N	\N	121062-08-6	\N	Melanocortin	t	26	2026-04-23 01:39:38.224978+00	\N
4f0af95e-6168-4b5b-b17d-ed3de646ad29	7b5d6fae-29d1-4f5a-ad73-45d9c80e3b51	Bremelanotide	9941379	\N	\N	189691-06-3	\N	Melanocortin	t	27	2026-04-23 01:39:38.224978+00	\N
4c7b1845-9bb5-4115-8586-cc521f8c0e83	008cf3b2-83bc-4e62-aa3e-69ffa21f70ef	Afamelanotide	16197727	\N	\N	75921-69-6	\N	Melanocortin	t	28	2026-04-23 01:39:38.224978+00	\N
ca5665ce-3b04-4465-b302-62f2d3d59aaf	b930d03c-144e-4d94-870b-edbec85fe185	Setmelanotide	11993702	\N	\N	920014-72-8	\N	Melanocortin	t	29	2026-04-23 01:39:38.224978+00	\N
f3518ad7-0ab3-4042-8690-5ec098bd1b06	24dfdba4-804a-4ec6-a07a-09ab1d4a2754	Gonadorelin	638793	\N	\N	33515-09-2	\N	Reproductive	t	30	2026-04-23 01:39:38.224978+00	\N
eb89f2a6-9ada-493a-97d5-a50b2354cb44	0d496904-5af9-49b4-b5b9-965e5771f415	Leuprolide	657181	\N	\N	53714-56-0	\N	Reproductive	t	31	2026-04-23 01:39:38.224978+00	\N
bad4fedc-04e6-45b9-91f9-acb5dbc8c5f1	e090299a-fc4e-44af-926e-023990b3f1dd	Triptorelin	25074470	\N	\N	57773-63-4	\N	Reproductive	t	32	2026-04-23 01:39:38.224978+00	\N
e9ec0e15-b141-434a-a25e-02e760ac9a6b	8641f300-b0d6-49eb-a748-a8f7259d4d71	Buserelin	50225	\N	\N	57982-77-1	\N	Reproductive	t	33	2026-04-23 01:39:38.224978+00	\N
6b241265-58a5-4e9b-865a-bb1869a77dac	ab2145ba-4ab2-4d3f-a8cc-597530e5d16f	Nafarelin	25077405	\N	\N	76932-56-4	\N	Reproductive	t	34	2026-04-23 01:39:38.224978+00	\N
87e6cbcb-ba89-45a5-b8d9-22eae0e1b4d1	d517270b-8337-4fae-8de5-320d6314d72a	Histrelin	25077993	\N	\N	76712-82-8	\N	Reproductive	t	35	2026-04-23 01:39:38.224978+00	\N
8497b0bf-f82e-462a-83d1-676a266f440a	d6927c4f-4b48-4982-9b64-e8eef8c5a257	Degarelix	16136245	\N	\N	214766-78-6	\N	Reproductive	t	36	2026-04-23 01:39:38.224978+00	\N
8ba01712-7fb2-4c33-83ae-372b65d20343	6744ebde-4b20-4ff3-a805-bf4a0a7cadf6	Cetrorelix	25074887	\N	\N	120287-85-6	\N	Reproductive	t	37	2026-04-23 01:39:38.224978+00	\N
ddfe5b0c-56e6-4947-97bf-b69bc018c63e	7577cf9d-03c1-4ad5-9271-881db956ec6d	Glucagon	16132283	\N	\N	16941-32-5	\N	Reproductive	t	38	2026-04-23 01:39:38.224978+00	\N
b9a9a17b-fc3b-4712-be03-cfd4838c8066	2b4eddc5-5dae-4167-8f57-84f27a94a123	Oxytocin	439302	\N	\N	50-56-6	\N	Hormones	t	39	2026-04-23 01:39:38.224978+00	\N
3966f0bf-8889-4ad6-8134-55866393e963	3601c714-ebfd-468b-bdb1-f1bdb58be945	Vasopressin	644077	\N	\N	11000-17-2	\N	Hormones	t	40	2026-04-23 01:39:38.224978+00	\N
b5e6d59f-affd-4373-b631-a8be85e6bccc	57cea345-978f-4b5e-a469-d82da924f66e	Desmopressin	5311065	\N	\N	16679-58-6	\N	Hormones	t	41	2026-04-23 01:39:38.224978+00	\N
27345b0a-82a9-4bb1-9268-8e09d32db876	16e5b7b1-80d0-4247-827e-5917479c912a	Calcitonin (Salmon)	16220016	\N	\N	47931-85-1	\N	Hormones	t	42	2026-04-23 01:39:38.224978+00	\N
5a86c6e2-389b-4175-984f-2fa62c2b7a43	b5f6a98e-515b-4bfe-9b72-e975aa3ab234	Kisspeptin-10	25240297	\N	\N	374675-21-5	\N	Hormones	t	43	2026-04-23 01:39:38.224978+00	\N
cea942cc-ac64-4d37-aa8a-9756927942ac	766a28b7-34d0-4074-b7c0-6c7ca50b751f	Pramlintide	70691388	\N	\N	151126-32-8	\N	Hormones	t	44	2026-04-23 01:39:38.224978+00	\N
33e12c6f-4caa-468c-a4cf-d8eda36a8b51	d8cd4d62-aa2e-49ad-a1ea-68eb3dde405b	Thymulin	71300623	\N	\N	63958-90-7	\N	Immune	t	45	2026-04-23 01:39:38.224978+00	\N
e08cb369-ab40-4b16-b695-5930d1187f35	9d3663e1-7fe3-4fb3-9d1e-555c0b3cd458	LL-37	16198951	\N	\N	2762-77-8	\N	Immune	t	46	2026-04-23 01:39:38.224978+00	\N
febba7a9-b65b-430a-bd6e-d60b539ee19f	f9aa33ba-221e-4678-8f4b-0f56306d1da6	Humanin	16131438	\N	\N	330936-69-1	\N	Immune	t	47	2026-04-23 01:39:38.224978+00	\N
59957478-16e7-4ae7-becc-509d2d8e090b	aed55dc7-bb86-41cd-9481-ecfae9a8027a	Eptifibatide	448812	\N	\N	148031-34-9	\N	Immune	t	48	2026-04-23 01:39:38.224978+00	\N
\.


--
-- Data for Name: sds_sections; Type: TABLE DATA; Schema: public; Owner: -
--

COPY public.sds_sections (id, compound_id, handling_precautions, storage_conditions, incompatibilities, exposure_limits, engineering_controls, ppe_respiratory, ppe_hands, ppe_eyes, ppe_skin, acute_toxicity, skin_corrosion, eye_damage, sensitization, carcinogenicity, reproductive_toxicity, target_organ, ecotoxicity, persistence, bioaccumulation, section7_source, section8_source, section11_source, section12_source, created_at, updated_at, deleted_at) FROM stdin;
b5025eb9-c6ab-44ae-98c7-4eef79946d34	008cf3b2-83bc-4e62-aa3e-69ffa21f70ef	\N	\N	\N	\N	\N	\N	\N	\N	\N	\N	\N	\N	\N	\N	\N	\N	\N	\N	\N	pubchem	pubchem	pubchem	pubchem	2026-04-25 01:16:21.499261+00	2026-04-25 01:16:21.39+00	\N
22e57146-549c-4c43-a808-a46454daaa65	2db3733b-2f29-4277-9471-6702235ed1a3	\N	Keep container tightly closed in a dry and well-ventilated place. Storage class (TRGS 510): 11 - Combustible Solids. Commercially available methylene blue 10-mg/mL solution for IV use should be stored at 20-25 °C, but may be exposed to temperatures ranging from 15-30 °C.	\N	\N	\N	Eye/face protection: Use equipment for eye protection tested and approved under appropriate government standards such as NIOSH (US) or EN 166(EU). Skin protection: Handle with gloves. Body Protection: Impervious clothing. The type of protective equipment must be selected according to the concentrati	\N	\N	\N	\N	\N	\N	\N	Evaluation: No data were available to the Working Group for humans. There is limited evidence for the carcinogenicity of methylene blue in experimental animals. Overall evaluation: Methylene blue is not classifiable as to its carcinogenicity in humans (Group 3).	\N	\N	LC50; Species: Penaeus californiensis (Shrimp) age 6 months, weight 2.54 g; Conditions: saltwater, static, 27 °C, salinity 24 ppt; Concentration: 100,000 ug/L for 1 hr LC50; Species: Heteropneustes fossilis (Indian catfish) adult, weight 22.2 g, length 18.3 cm; Conditions: freshwater, renewal, 18-22 °C; Concentration: 188500 ug/L for 24 hr (95% confidence interval: 184260-192840 ug/L) /formulated product/ LC50; Species: Heteropneustes fossilis (Indian catfish) adult, weight 22.2 g, length 18.3 c	ANAEROBIC: The objective of this study is to evaluate the decolorization of Methylene Blue (MB) by an up-flow anaerobic sludge blanket (UASB) reactor. The UASB reactor was operated under batch condition with total treatment volume of 3 L and operation time of 24 hrs per batch. It was found that the color of MB disappeared within a few minutes after entering into the UASB reactor due to reduction b	An estimated BCF of 3 was calculated in fish for methylene blue(SRC), using an estimated log Kow of 0.75(1) and a regression-derived equation(1). According to a classification scheme(2), this BCF suggests the potential for bioconcentration in aquatic organisms is low(SRC). The aquatic plant, Hydrilla verticillata was shown to remove methylene blue from aqueous solution rapidly; 100, 500, and 1000	pubchem	pubchem	pubchem	pubchem	2026-05-05 14:24:40.118027+00	2026-05-05 14:24:39.848+00	\N
\.


--
-- Data for Name: side_effects; Type: TABLE DATA; Schema: public; Owner: -
--

COPY public.side_effects (id, name, description, severity_level, frequency, category, color_bg, color_text, icon, sort_order, is_active, deleted_at, created_at, updated_at) FROM stdin;
1	Injection Site Reaction	Mild redness or swelling at injection site	mild	common	Local	#E8F5E8	#2E7D32	Shield	1	t	\N	2025-07-15 17:14:31+00	2025-07-24 02:57:30+00
2	Nausea	Mild to moderate nausea, especially when starting	moderate	uncommon	Gastrointestinal	#FFF3E0	#EF6C00	Shield	2	t	\N	2025-07-15 17:14:31+00	2025-07-24 02:57:34+00
3	Headache	Mild headache, usually temporary	mild	uncommon	Neurological	#FFF8E1	#FF8F00	Shield	3	t	\N	2025-07-15 17:14:31+00	2025-07-28 23:30:26+00
4	Fatigue	Temporary fatigue during initial weeks	critical	rare	Systemic	#E3F2FD	#1565C0	Shield	4	t	\N	2025-07-15 17:14:31+00	2025-07-28 23:35:14+00
13	test	\N	mild	uncommon	Cardiovascular	#E0F7FA	#0097A7	ClipboardList	0	t	\N	2025-07-24 03:07:49+00	2025-08-11 22:47:42+00
14	Inflammation	Activation of leukocytes leading to increased cytokine production.	moderate	common	Immune system	#FEF2F2	#DC2626	Shield	0	t	\N	2025-08-07 20:44:52+00	2025-08-07 20:44:52+00
15	Autoimmunity	TLR activation leading to triggering or worsening of autoimmunity.	severe	rare	Immune system	#FEF2F2	#DC2626	Shield	0	t	\N	2025-08-07 20:47:00+00	2025-08-07 20:47:00+00
16	Insomnia	\N	mild	uncommon	Neurological	#FEF2F2	#DC2626	Shield	0	t	\N	2025-08-08 00:43:34+00	2025-08-08 00:43:34+00
17	High Blood Pressure	\N	moderate	uncommon	Cardiovascular	#FEF2F2	#DC2626	Shield	0	t	\N	2025-08-08 00:44:51+00	2025-08-08 00:44:51+00
18	Tachycardia	\N	severe	rare	Cardiovascular	#FEF2F2	#DC2626	Shield	0	t	\N	2025-08-08 00:45:26+00	2025-08-08 00:48:43+00
20	Constipation	\N	moderate	common	Gastrointestinal	#FEF2F2	#DC2626	Shield	0	t	\N	2025-08-20 00:45:11+00	2025-08-20 00:45:11+00
21	Fever	\N	severe	uncommon	Immunological	#FEF2F2	#DC2626	Shield	0	t	\N	2025-08-21 16:08:54+00	2025-08-21 16:08:54+00
22	Liver stress	\N	moderate	uncommon	Liver	#FEF2F2	#DC2626	Shield	0	t	\N	2025-08-21 16:09:10+00	2025-08-21 16:09:10+00
23	Aggravation of existing Tumors	Be aware of this possibility if you have family history of cancer or have dealt with it yourself.	critical	rare	Cancer	#FEF2F2	#DC2626	Shield	0	t	\N	2025-08-22 01:08:47+00	2025-08-22 01:09:46+00
24	Hypoglycemia	\N	critical	uncommon	Blood Glucose	#FEF2F2	#DC2626	Shield	0	t	\N	2025-08-23 02:25:55+00	2025-08-23 02:25:55+00
25	Loss of appetite	\N	moderate	very_common	Gastrointestinal	#FEF2F2	#DC2626	Shield	0	t	\N	2025-08-23 03:02:01+00	2025-08-23 03:02:01+00
26	Apathy	\N	moderate	uncommon	\N	#FEF2F2	#DC2626	Shield	0	t	\N	2025-08-27 21:25:49+00	2025-08-27 21:25:49+00
27	Itchiness/Irritation	\N	mild	uncommon	Dermatological	#FEF2F2	#DC2626	Shield	0	t	\N	2025-08-30 07:59:07+00	2025-08-30 08:01:54+00
28	Drowsiness	\N	moderate	uncommon	Sleep	#FEF2F2	#DC2626	Shield	0	t	\N	2025-08-30 07:59:29+00	2025-08-30 07:59:29+00
29	Hypotension	\N	severe	rare	Cardiovascular	#FEF2F2	#DC2626	Shield	0	t	\N	2025-08-30 12:39:55+00	2025-08-30 12:40:14+00
30	Arthralgia	\N	severe	uncommon	Rheumatology	#FEF2F2	#DC2626	Shield	0	t	\N	2025-08-31 21:00:47+00	2025-08-31 21:00:47+00
31	Connective Tissue Injury	\N	critical	rare	\N	#FEF2F2	#DC2626	Shield	0	t	\N	2025-09-07 21:41:25+00	2025-09-07 21:41:25+00
32	Diarrhea	\N	moderate	common	Gastrointestinal	#FEF2F2	#DC2626	Shield	0	t	\N	2025-09-07 23:09:47+00	2025-09-07 23:09:47+00
33	Serotonin Syndrome	Serotonin syndrome is a rare but serious neurological emergency caused by excessive serotonin, featuring symptoms like agitation, tremors, rapid heart rate, and confusion, often from drug interactions.	critical	rare	Neurological/Psychiatric Emergency	#FEF2F2	#DC2626	Activity	5	t	\N	2025-10-24 22:08:42+00	2025-10-24 22:11:57+00
34	Blood Clots	Blood clots are thickened masses of blood that form inside blood vessels, potentially obstructing flow and leading to serious health issues such as deep vein thrombosis or pulmonary embolism. Seek immediate medical attention if suspected.	critical	rare	Thrombotic	#FEF2F2	#DC2626	Shield	5	t	\N	2025-10-24 22:17:43+00	2025-10-24 22:17:43+00
35	Gynecomastia	Gynecomastia is the enlargement of breast tissue in males, often caused by increased estrogen levels or decreased testosterone, and may lead to discomfort or psychological distress.	moderate	uncommon	Endocrinology	#FEF2F2	#DC2626	User	5	t	\N	2025-10-24 22:20:46+00	2025-10-24 22:20:46+00
36	Edema	Edema is the swelling caused by excess fluid trapped in body tissues, often due to circulatory issues, hormonal imbalances, or kidney problems, and may lead to discomfort or tightness.	mild	uncommon	Cardiovascular	#FEF2F2	#DC2626	Activity	5	t	\N	2025-10-24 22:28:13+00	2025-10-24 22:28:13+00
37	Priapism	Priapism is a prolonged, often painful erection lasting over 4 hours, unrelated to sexual stimulation, classified as an urgent urological emergency that may result from blood flow issues or medication side effects. Seek immediate medical help to prevent complications.	severe	rare	Urology	#FEF2F2	#DC2626	User	5	t	\N	2025-10-24 22:33:58+00	2025-10-24 22:33:58+00
38	Addiction and Dependency	\N	critical	very_common	Habit  Formation	#FEF2F2	#DC2626	Shield	0	t	\N	2025-11-04 17:37:11+00	2025-11-04 17:37:11+00
39	Motor Control Loss	\N	severe	common	Coordination	#FEF2F2	#DC2626	Shield	0	t	\N	2025-11-04 17:37:41+00	2025-11-04 17:37:41+00
40	Disinhibition	\N	moderate	very_common	Behavioral	#FEF2F2	#DC2626	Shield	0	t	\N	2025-11-04 17:38:26+00	2025-11-04 17:38:26+00
41	Memory Gaps	\N	severe	very_common	Cognitive	#FEF2F2	#DC2626	Shield	0	t	\N	2025-11-05 05:37:16+00	2025-11-05 05:37:16+00
42	Dry Mouth	\N	mild	rare	Sensation	#FEF2F2	#DC2626	Shield	0	t	\N	2025-11-15 01:55:34+00	2025-11-15 01:55:34+00
43	Muscle Pain	\N	moderate	common	Orthopedics	#FEF2F2	#DC2626	Shield	0	t	\N	2025-11-29 12:04:30+00	2025-11-29 12:04:30+00
44	Stuffy Nose	\N	mild	common	ENT	#FEF2F2	#DC2626	Shield	0	t	\N	2025-11-29 12:05:30+00	2025-11-29 12:05:30+00
45	HPA Axis Supression	\N	mild	rare	Adrenal	#FEF2F2	#DC2626	Shield	0	t	\N	2025-12-13 16:42:58+00	2025-12-13 16:42:58+00
46	Heart Palpitations	\N	moderate	uncommon	Cardiovascular	#FEF2F2	#DC2626	Shield	0	t	\N	2025-12-13 17:17:04+00	2025-12-13 17:17:04+00
47	Shortness Of Breath	\N	severe	uncommon	Pulmanory	#FEF2F2	#DC2626	Shield	0	t	\N	2025-12-13 17:17:19+00	2025-12-13 17:17:19+00
48	UTI	\N	moderate	uncommon	\N	#FEF2F2	#DC2626	Shield	0	t	\N	2025-12-18 23:36:17+00	2025-12-18 23:36:17+00
49	Fungal Infections	\N	mild	uncommon	Genital	#FEF2F2	#DC2626	Shield	0	t	\N	2025-12-18 23:36:30+00	2025-12-18 23:36:30+00
50	Diuresis	\N	mild	uncommon	\N	#FEF2F2	#DC2626	Shield	0	t	\N	2025-12-18 23:36:43+00	2025-12-18 23:36:43+00
51	Brain Fog	\N	moderate	common	\N	#FEF2F2	#DC2626	Shield	0	t	\N	2025-12-21 00:53:20+00	2025-12-21 00:53:20+00
\.


--
-- Data for Name: stripe_customers; Type: TABLE DATA; Schema: public; Owner: -
--

COPY public.stripe_customers (id, user_id, stripe_customer_id, created_at, updated_at) FROM stdin;
\.


--
-- Data for Name: subscription_events; Type: TABLE DATA; Schema: public; Owner: -
--

COPY public.subscription_events (id, stripe_event_id, event_type, subscription_id, user_id, stripe_subscription_id, payload, previous_status, new_status, processed_at, processing_error, created_at, source_type, source_id) FROM stdin;
\.


--
-- Data for Name: subscriptions; Type: TABLE DATA; Schema: public; Owner: -
--

COPY public.subscriptions (id, user_id, stripe_subscription_id, stripe_customer_id, stripe_product_id, stripe_price_id, status, cancel_at_period_end, current_period_start, current_period_end, canceled_at, trial_end, metadata, created_at, updated_at) FROM stdin;
\.


--
-- Data for Name: user_roles; Type: TABLE DATA; Schema: public; Owner: -
--

COPY public.user_roles (id, user_id, role_id, app_context, granted_by, granted_at, expires_at, is_active, created_at) FROM stdin;
5	0528557a-5216-45f1-91ee-c293a95af1b0	1	calculator	\N	2026-04-28 21:47:16.927+00	\N	t	2026-04-28 21:47:16.927+00
6	e70508c1-9ddf-4ffc-b84c-1f96aaa54b2f	1	calculator	\N	2026-04-28 21:50:36.95+00	\N	t	2026-04-28 21:50:36.95+00
7	1bcf4777-9ddf-461c-ab6b-ac17e8dcfef4	1	calculator	\N	2026-04-28 21:55:14.784+00	\N	t	2026-04-28 21:55:14.784+00
8	fd0b3399-eb5f-416e-b270-11fc6d004c63	1	calculator	\N	2026-04-28 22:08:31.671+00	\N	t	2026-04-28 22:08:31.671+00
9	342749e0-e1a7-403c-8bc1-a276cd712fcf	1	calculator	\N	2026-04-28 22:15:19.459+00	\N	t	2026-04-28 22:15:19.459+00
11	2e34bfb0-482d-48d8-94a7-9f464c0b1f60	2	wiki	\N	2026-05-01 19:37:09.882+00	\N	t	2026-05-01 19:37:09.882+00
12	d51a6f46-da6c-48ec-98e9-82cfb0f281ac	1	calculator	\N	2026-05-02 17:47:47.977+00	\N	t	2026-05-02 17:47:47.977+00
16	25654e62-896e-4280-a123-ce80bdc1d017	1	sds-app	\N	2026-05-05 14:47:25.347376+00	\N	t	2026-05-05 14:47:25.347376+00
\.


--
-- Data for Name: user_suggestions; Type: TABLE DATA; Schema: public; Owner: -
--

COPY public.user_suggestions (id, email, user_id, suggestion_text, entity_type, entity_name, entity_slug, page_url, status, admin_notes, reviewed_by, reviewed_at, created_at, updated_at, app_source) FROM stdin;
1	carlos.jaramillo18@yahoo.com	\N	test	peptide	5-Amino-1MQ	5-amino-1mq	http://localhost:3002/peptide/5-amino-1mq	pending	\N	\N	\N	2026-04-23 01:51:43.092273+00	2026-04-23 01:51:43.092273+00	wiki
\.


--
-- Data for Name: users; Type: TABLE DATA; Schema: public; Owner: -
--

COPY public.users (id, auth_user_id, email, first_name, last_name, image_url, phone, is_active, email_verified, last_login_at, created_at, updated_at, deleted_at) FROM stdin;
2e34bfb0-482d-48d8-94a7-9f464c0b1f60	84088e38-316a-46eb-87c0-d44ee489aaba	ajaramilloportilla18@gmail.com	Admin	Wiki	\N	\N	t	t	\N	2026-04-23 01:28:32.58654+00	2026-04-23 01:28:32.58654+00	\N
8ad8fd0e-1ef0-4378-a879-a1bcc852de1b	eb7b7c35-fd19-457c-92f0-87a0d1a696a5	jonasmartha805@gmail.com			\N	\N	t	t	\N	2026-04-23 01:28:32.58654+00	2026-04-23 01:28:32.58654+00	\N
6965740d-e92b-421a-af2d-cb81c24792b3	2ab7af5f-8591-42af-ac96-f2c719ac2dfa	cjaramilloportilla@gmail.com	Carlos	Jara	\N	\N	t	t	\N	2026-04-23 04:45:09.353032+00	2026-04-25 01:13:45.597+00	\N
0528557a-5216-45f1-91ee-c293a95af1b0	calc_device_741995c8-d08b-439e-8377-7875fefaf44c	741995c8-d08b-439e-8377-7875fefaf44c@calculator.pepti.app	Calculator	User	\N	\N	t	f	\N	2026-04-28 21:47:14.874+00	2026-04-28 21:47:14.874+00	\N
e70508c1-9ddf-4ffc-b84c-1f96aaa54b2f	calc_device_bc3ba80e-f9ff-475e-bc6d-e066ad9b2a6c	bc3ba80e-f9ff-475e-bc6d-e066ad9b2a6c@calculator.pepti.app	Calculator	User	\N	\N	t	f	\N	2026-04-28 21:50:35.337+00	2026-04-28 21:50:35.337+00	\N
fd0b3399-eb5f-416e-b270-11fc6d004c63	calc_device_822764fc-451d-4992-a268-4c69b7e92ab9	822764fc-451d-4992-a268-4c69b7e92ab9@calculator.pepti.app	Calculator	User	\N	\N	t	f	2026-04-28 22:08:33.885+00	2026-04-28 22:08:31.544+00	2026-04-28 22:08:33.885+00	\N
342749e0-e1a7-403c-8bc1-a276cd712fcf	calc_device_d814e1e5-9d99-4fa2-adfd-a420613a18df	d814e1e5-9d99-4fa2-adfd-a420613a18df@calculator.pepti.app	Calculator	User	\N	\N	t	f	2026-04-28 22:15:21.876+00	2026-04-28 22:15:19.335+00	2026-04-28 22:15:21.876+00	\N
1bcf4777-9ddf-461c-ab6b-ac17e8dcfef4	calc_device_0774cac6-11cd-45a9-aed2-9da902300b01	0774cac6-11cd-45a9-aed2-9da902300b01@calculator.pepti.app	Calculator	User	\N	\N	t	f	2026-05-02 17:50:20.208+00	2026-04-28 21:55:13.253+00	2026-05-02 17:50:20.208+00	\N
d51a6f46-da6c-48ec-98e9-82cfb0f281ac	calc_device_e964bf59-12c4-4b06-8b76-d2b6a6897268	e964bf59-12c4-4b06-8b76-d2b6a6897268@calculator.pepti.app	Calculator	User	\N	\N	t	f	2026-05-02 17:50:27.04+00	2026-05-02 17:47:46.183+00	2026-05-02 17:50:27.04+00	\N
25654e62-896e-4280-a123-ce80bdc1d017	29f30b4b-c08c-4129-8cf3-3e4a2978ad7e	carlos.jaramillo18@yahoo.com	Carlos	Jaramillo	\N	\N	t	f	\N	2026-05-05 14:47:25.347376+00	2026-05-05 14:54:37.070238+00	\N
\.


--
-- Data for Name: vendor_peptides; Type: TABLE DATA; Schema: public; Owner: -
--

COPY public.vendor_peptides (id, vendor_id, peptide_id, shopnow_link, product_photo, purity, weight, certificate_of_authenticity_link, deleted_at, created_at, updated_at) FROM stdin;
470	89	116	https://stratelabs.is/product/semaglutide-by-semathin-10mg/	https://stratelabs.is/wp-content/uploads/2025/06/WhatsApp-Image-2025-05-04-at-05.37.36_e8bda194.jpg	99.578%	11.02mg	https://stratelabs.is/wp-content/uploads/2025/06/Test-Report-68569.png	\N	2025-11-02 04:16:00+00	2025-11-02 04:16:00+00
490	95	175	https://www.madebythrone.com/products/throne-ptd-bdm-hair-serum	https://www.madebythrone.com/cdn/shop/files/ptdbdm.png	\N	\N	\N	\N	2025-11-14 07:52:37+00	2025-11-14 07:52:37+00
626	89	204	https://stratelabs.is/product/enclomiphene-capsules-12-5mg-x60/	https://stratelabs.is/wp-content/uploads/2024/11/enclomiphene.png	94.45%	12.5mg	https://stratelabs.is/wp-content/uploads/2021/07/Enclom-2025.png	\N	2025-12-14 17:51:31+00	2025-12-14 17:51:31+00
789	93	197	https://ruo.bio/product/sm04554-0-25-2-5mg-ml-30ml/	https://ruo.bio/wp-content/uploads/2025/10/sm04554-1000x1000.png	\N	0.317%	https://ruo.bio/wp-content/uploads/2026/01/Chromate_Job_31053.png	\N	2026-01-24 04:39:42+00	2026-01-24 04:39:42+00
836	96	183	https://arcanepeptides.com/product/phenibut/	https://arcanepeptides.com/wp-content/uploads/2026/01/Render_Mockup_4000_4000_2026-01-23-1000x1000.png	\N	40g	\N	\N	2026-02-05 19:30:37+00	2026-02-05 19:30:37+00
860	93	117	https://ruo.bio/product/ace-031-1mg/	https://ruo.bio/wp-content/uploads/2025/09/ace031-1536x1536.png	99.505%	1.28mg	https://ruo.bio/wp-content/uploads/2025/09/Test-Report-100903.png	\N	2026-02-06 00:22:09+00	2026-02-06 00:22:09+00
862	93	216	https://ruo.bio/product/ahk-cu-100mg-coming-soon/	https://ruo.bio/wp-content/uploads/2025/12/ahkcu-1536x1536.png	\N	103.2	https://ruo.bio/wp-content/uploads/2025/12/Chromate_Job_30391.png	\N	2026-02-06 00:22:55+00	2026-02-06 00:22:55+00
863	93	133	https://ruo.bio/product/aicar-50mg-coming-soon/	https://ruo.bio/wp-content/uploads/2025/10/aicar-1536x1536.png	\N	50mg	\N	\N	2026-02-06 00:23:53+00	2026-02-06 00:23:53+00
866	93	107	https://ruo.bio/product/ara-290-10mg/	https://ruo.bio/wp-content/uploads/2025/09/ara290-1536x1536.png	99.716%	9.32mg	https://ruo.bio/wp-content/uploads/2025/09/Test-Report-64291.png	\N	2026-02-06 00:24:33+00	2026-02-06 00:24:33+00
867	93	125	https://ruo.bio/product/b7-33-10mg/	https://ruo.bio/wp-content/uploads/2025/09/b733-1536x1536.png	99%	10mg	\N	\N	2026-02-06 00:24:51+00	2026-02-06 00:24:51+00
874	93	148	https://ruo.bio/product/bronchogen/	https://ruo.bio/wp-content/uploads/2025/09/bronchogen-1536x1536.png	\N	20mg	\N	\N	2026-02-06 00:26:49+00	2026-02-06 00:26:49+00
875	93	208	https://ruo.bio/product/cagrilintide/	https://ruo.bio/wp-content/uploads/2025/09/cagri10-1536x1536.png	99.817%	10.45mg	https://ruo.bio/wp-content/uploads/2025/11/Test-Report-87500.png	\N	2026-02-06 00:27:10+00	2026-02-06 00:27:10+00
876	93	201	https://ruo.bio/product/cb0301/	https://ruo.bio/wp-content/uploads/2025/11/cb0301-1536x1536.png	\N	5%	\N	\N	2026-02-06 00:27:33+00	2026-02-06 00:27:33+00
877	93	181	https://ruo.bio/product/cerebroprotein-hydrolysate-215mg/	https://ruo.bio/wp-content/uploads/2025/09/cerebro-1536x1536.png	\N	215mg	\N	\N	2026-02-06 00:27:51+00	2026-02-06 00:27:51+00
878	93	151	https://ruo.bio/product/chonluten/	https://ruo.bio/wp-content/uploads/2026/01/chonluten-1536x1536.png	\N	20mg	\N	\N	2026-02-06 00:28:05+00	2026-02-06 00:28:05+00
888	93	145	https://ruo.bio/product/crytagen/	https://ruo.bio/wp-content/uploads/2025/09/crystagen-1536x1536.png	\N	20mg	\N	\N	2026-02-06 00:31:07+00	2026-02-06 00:31:07+00
890	93	207	https://ruo.bio/product/dnsp-11-10mg/	https://ruo.bio/wp-content/uploads/2025/09/dnsp11-1536x1536.png	\N	10mg	\N	\N	2026-02-06 00:31:49+00	2026-02-06 00:31:49+00
894	93	134	https://ruo.bio/product/epithalon/	https://ruo.bio/wp-content/uploads/2025/09/epithalon-1536x1536.png	99%	10mg	\N	\N	2026-02-06 00:32:45+00	2026-02-06 00:32:45+00
895	89	134	https://stratelabs.is/product/epitalon-10mg/	https://stratelabs.is/wp-content/uploads/2024/11/EPITALON.png	99.51%	13.45mg	https://stratelabs.is/wp-content/uploads/2023/01/Test-Report-74878-1.png	\N	2026-02-06 00:32:45+00	2026-02-06 00:32:45+00
896	93	177	https://ruo.bio/product/fgl/	https://ruo.bio/wp-content/uploads/2025/09/fgl-1-1536x1536.png	\N	10mg	\N	\N	2026-02-06 00:33:00+00	2026-02-06 00:33:00+00
897	93	156	https://ruo.bio/product/follistatin-344-1mg/	https://ruo.bio/wp-content/uploads/2025/09/fsh1-1536x1536.png	99%	1mg	\N	\N	2026-02-06 00:33:16+00	2026-02-06 00:33:16+00
898	93	124	https://ruo.bio/product/fox04-dri-10mg/	https://ruo.bio/wp-content/uploads/2025/09/fox04-1536x1536.png	99.232%	10.56mg	https://ruo.bio/wp-content/uploads/2025/09/Test-Report-64292.png	\N	2026-02-06 00:33:33+00	2026-02-06 00:33:33+00
915	93	200	https://ruo.bio/product/humanin/	https://ruo.bio/wp-content/uploads/2025/11/humanin-1536x1536.png	98.477%	8.22mg	https://ruo.bio/wp-content/uploads/2026/01/Test-Report-100909.png	\N	2026-02-06 00:36:47+00	2026-02-06 00:36:47+00
923	93	206	https://ruo.bio/product/kisspeptin-10mg/	https://ruo.bio/wp-content/uploads/2025/09/kisspeptin-1-1536x1536.png	\N	10mg	\N	\N	2026-02-06 00:39:43+00	2026-02-06 00:39:43+00
929	93	140	https://ruo.bio/product/livagen/	https://ruo.bio/wp-content/uploads/2025/09/livagen-1536x1536.png	\N	20mg	\N	\N	2026-02-06 00:40:51+00	2026-02-06 00:40:51+00
930	93	103	https://ruo.bio/product/ll-37-5mg/	https://ruo.bio/wp-content/uploads/2025/09/ll37-1536x1536.png	99.036%	4.86mg	https://ruo.bio/wp-content/uploads/2026/01/Test-Report-100910.png	\N	2026-02-06 00:41:06+00	2026-02-06 00:41:06+00
931	93	127	https://ruo.bio/product/mazdutide/	https://ruo.bio/wp-content/uploads/2025/09/mazdu-1536x1536.png	99.826%	10.46mg	https://ruo.bio/wp-content/uploads/2025/11/Test-Report-87512.png	\N	2026-02-06 00:41:34+00	2026-02-06 00:41:34+00
932	89	127	https://stratelabs.is/product/mazdutide-10mg/	https://stratelabs.is/wp-content/uploads/2024/11/maz.jpg	98.033%	10.54mg	https://stratelabs.is/wp-content/uploads/2024/11/Test-Report-45003-1.png	\N	2026-02-06 00:41:34+00	2026-02-06 00:41:34+00
938	93	188	https://ruo.bio/product/meldonium-dihydrate-500mg-60-units/	https://ruo.bio/wp-content/uploads/2025/12/Chromate_Job_31517-1-1569x2048.png	\N	500mg	\N	\N	2026-02-06 00:44:05+00	2026-02-06 00:44:05+00
943	93	114	https://ruo.bio/product/mtp131/	https://ruo.bio/wp-content/uploads/2025/09/mtp-1536x1536.png	99.811%	11.74mg	https://ruo.bio/wp-content/uploads/2025/11/Test-Report-87527.png	\N	2026-02-06 00:46:11+00	2026-02-06 00:46:11+00
947	93	165	https://ruo.bio/product/ovagen/	https://ruo.bio/wp-content/uploads/2025/09/ovagen-1536x1536.png	\N	20mg	\N	\N	2026-02-06 00:47:06+00	2026-02-06 00:47:06+00
949	93	106	https://ruo.bio/product/p-21-5mg/	https://ruo.bio/wp-content/uploads/2025/09/p-21-1536x1536.png	\N	5mg	\N	\N	2026-02-06 01:03:18+00	2026-02-06 01:03:18+00
950	93	149	https://ruo.bio/product/pancragen/	https://ruo.bio/wp-content/uploads/2025/09/pancragen-1536x1536.png	\N	20mg	\N	\N	2026-02-06 01:03:35+00	2026-02-06 01:03:35+00
951	93	118	https://ruo.bio/product/pe-22-28/	https://ruo.bio/wp-content/uploads/2025/09/pe2228-1536x1536.png	99.224%	9.451mg	https://ruo.bio/wp-content/uploads/2025/11/Chromate_Job_29554.png	\N	2026-02-06 01:03:49+00	2026-02-06 01:03:49+00
952	89	118	https://stratelabs.is/product/pe-22-28-10mg/	https://stratelabs.is/wp-content/uploads/2025/08/PE222810MG2ML16x.png	99.916%	10.88mg	https://stratelabs.is/wp-content/uploads/2025/08/Test-Report-74903-2.png	\N	2026-02-06 01:03:49+00	2026-02-06 01:03:49+00
955	93	135	https://ruo.bio/product/pinealon/	https://ruo.bio/wp-content/uploads/2025/09/pinealon-1536x1536.png	\N	20mg	\N	\N	2026-02-06 01:04:29+00	2026-02-06 01:04:29+00
956	93	119	https://ruo.bio/product/pnc-27-5mg/	https://ruo.bio/wp-content/uploads/2025/09/pnc27-1536x1536.png	99.220%	4.27mg	https://ruo.bio/wp-content/uploads/2026/01/Test-Report-100914.png	\N	2026-02-06 01:04:58+00	2026-02-06 01:04:58+00
967	96	205	https://arcanepeptides.com/product/snap8/	https://arcanepeptides.com/wp-content/uploads/2025/09/snap-1000x1000.png	\N	10mg	\N	\N	2026-02-06 01:06:32+00	2026-02-06 01:06:32+00
968	93	205	https://ruo.bio/product/snap8/	https://ruo.bio/wp-content/uploads/2025/09/snap8-1536x1536.png	99.631%	9.877mg	https://ruo.bio/wp-content/uploads/2026/01/Chromate_Job_30897.png	\N	2026-02-06 01:06:32+00	2026-02-06 01:06:32+00
969	93	129	https://ruo.bio/product/survodutide-10mg/	https://ruo.bio/wp-content/uploads/2025/09/survo-1536x1536.png	99.880%	10.45mg	https://ruo.bio/wp-content/uploads/2025/11/Test-Report-87510.png	\N	2026-02-06 01:06:45+00	2026-02-06 01:06:45+00
976	93	209	https://ruo.bio/product/testagen/	https://ruo.bio/wp-content/uploads/2025/09/testagen-1536x1536.png	\N	20mg	\N	\N	2026-02-06 01:07:35+00	2026-02-06 01:07:35+00
977	93	138	https://ruo.bio/product/thymalin/	https://ruo.bio/wp-content/uploads/2025/12/thymalin-1536x1536.png	\N	20mg	\N	\N	2026-02-06 01:07:57+00	2026-02-06 01:07:57+00
978	93	130	https://ruo.bio/product/thymosin-alpha-1-5mg/	https://ruo.bio/wp-content/uploads/2025/09/ta1-1536x1536.png	\N	5mg	\N	\N	2026-02-06 01:08:11+00	2026-02-06 01:08:11+00
979	89	130	https://stratelabs.is/product/thymosin-alpha-1-12-5mg/	https://stratelabs.is/wp-content/uploads/2025/11/WhatsApp-Image-2025-11-11-at-13.49.41_bb0289dc.jpg	\N	12.5mg	\N	\N	2026-02-06 01:08:11+00	2026-02-06 01:08:11+00
980	93	203	https://ruo.bio/product/topilutamide-2-20mg-ml-30ml/	https://ruo.bio/wp-content/uploads/2025/10/topil-1536x1536.png	\N	2.267%	https://ruo.bio/wp-content/uploads/2025/11/Chromate_Job_29214.png	\N	2026-02-06 01:08:23+00	2026-02-06 01:08:23+00
981	93	136	https://ruo.bio/product/vesugen/	https://ruo.bio/wp-content/uploads/2026/01/vesugen-1536x1536.png	\N	20mg	\N	\N	2026-02-06 01:08:35+00	2026-02-06 01:08:35+00
982	93	139	https://ruo.bio/product/vilon/	https://ruo.bio/wp-content/uploads/2026/01/vilon-1536x1536.png	\N	20mg	\N	\N	2026-02-06 01:08:45+00	2026-02-06 01:08:45+00
988	96	23	https://arcanepeptides.com/product/2381089-83-2/	https://arcanepeptides.com/wp-content/uploads/2025/09/reta-1000x1000.png	\N	10mg	\N	\N	2026-02-18 22:17:33+00	2026-02-18 22:17:33+00
989	93	23	https://ruo.bio/product/2381089-83-2/	https://ruo.bio/wp-content/uploads/2025/09/reta40-1536x1536.png	99.552%	38.16mg	https://ruo.bio/wp-content/uploads/2025/09/Test-Report-83260.png	\N	2026-02-18 22:17:33+00	2026-02-18 22:17:33+00
990	89	23	https://stratelabs.is/product/retatrutide-20mg/	https://stratelabs.is/wp-content/uploads/2024/07/WhatsApp-Image-2025-05-07-at-13.09.19_e82c0e86.jpg	99.933%	23.96mg	https://stratelabs.is/wp-content/uploads/2025/05/Test-Report-74899.png	\N	2026-02-18 22:17:33+00	2026-02-18 22:17:33+00
991	97	23	https://moglabs.bio/product/2381089-83-2/	https://moglabs.bio/wp-content/uploads/2025/09/reta-1000x1000.png	\N	10mg	\N	\N	2026-02-18 22:17:33+00	2026-02-18 22:17:33+00
992	93	113	https://ruo.bio/product/5-amino-1mq/	https://ruo.bio/wp-content/uploads/2025/11/5amino150mg-1536x1536.png	99.743%	52.94mg	https://ruo.bio/wp-content/uploads/2025/12/Chromate_Job_30245-1-scaled.png	\N	2026-02-18 22:18:28+00	2026-02-18 22:18:28+00
993	97	113	https://moglabs.bio/product/5-amino-1mq/	https://moglabs.bio/wp-content/uploads/2025/09/5amino1mq-1000x1000.png	\N	50mg	\N	\N	2026-02-18 22:18:28+00	2026-02-18 22:18:28+00
994	93	172	https://ruo.bio/product/acetic-acid/	https://ruo.bio/wp-content/uploads/2025/09/acetic10ml-4-1536x1536.png	\N	0.6%	\N	\N	2026-02-18 22:20:00+00	2026-02-18 22:20:00+00
995	97	172	https://moglabs.bio/product/acetic-acid/	https://moglabs.bio/wp-content/uploads/2025/09/acetic-1000x1000.png	\N	0.6%	\N	\N	2026-02-18 22:20:00+00	2026-02-18 22:20:00+00
996	96	115	https://arcanepeptides.com/product/aod-9604/	https://arcanepeptides.com/wp-content/uploads/2025/11/aod-1000x1000.png	99.770%	4.2mg	https://arcanepeptides.com/wp-content/uploads/2026/01/Test-Report-102679-1.png	\N	2026-02-18 22:21:10+00	2026-02-18 22:21:10+00
997	93	115	https://ruo.bio/product/aod-9604/	https://ruo.bio/wp-content/uploads/2025/09/aod5mg-1536x1536.png	99%	5mg	\N	\N	2026-02-18 22:21:10+00	2026-02-18 22:21:10+00
998	97	115	https://moglabs.bio/product/aod-9604/	https://moglabs.bio/wp-content/uploads/2025/09/aod-1000x1000.png	99.770%	4.2mg	https://moglabs.bio/wp-content/uploads/2026/02/Test-Report-102679-2.png	\N	2026-02-18 22:21:10+00	2026-02-18 22:21:10+00
999	96	171	https://arcanepeptides.com/product/bacteriostatic-water/	https://arcanepeptides.com/wp-content/uploads/2025/09/bacwater-1000x1000.png	\N	0.9%	\N	\N	2026-02-18 22:25:21+00	2026-02-18 22:25:21+00
1000	93	171	https://ruo.bio/product/bacteriostatic-water/	https://ruo.bio/wp-content/uploads/2025/09/30mlglass-2-1536x1536.png	\N	0.978%	https://ruo.bio/wp-content/uploads/2025/10/Test-Report-83275.png	\N	2026-02-18 22:25:21+00	2026-02-18 22:25:21+00
1001	97	171	https://moglabs.bio/product/bacteriostatic-water/	https://moglabs.bio/wp-content/uploads/2025/09/bacwater-1000x1000.png	\N	0.9%	\N	\N	2026-02-18 22:25:21+00	2026-02-18 22:25:21+00
1002	96	100	https://arcanepeptides.com/product/bpc-157/	https://arcanepeptides.com/wp-content/uploads/2025/09/bpc-1000x1000.png	\N	5mg	\N	\N	2026-02-18 22:26:35+00	2026-02-18 22:26:35+00
1003	93	100	https://ruo.bio/product/bpc-157/	https://ruo.bio/wp-content/uploads/2025/09/bpc157-1536x1536.png	99.206%	5.91mg	https://ruo.bio/wp-content/uploads/2025/10/Test-Report-83230.png	\N	2026-02-18 22:26:35+00	2026-02-18 22:26:35+00
1004	89	100	https://stratelabs.is/?s=bpc&post_type=product&product_cat=0	https://stratelabs.is/wp-content/uploads/2021/07/BPC-157-new-01-e1719343206622-2.png	99%	5.48mg	https://stratelabs.is/wp-content/uploads/2021/07/Test-Report-68568.png	\N	2026-02-18 22:26:35+00	2026-02-18 22:26:35+00
1005	95	100	https://www.madebythrone.com/products/bpc-157-capsules-30	https://www.madebythrone.com/cdn/shop/files/THRONE-PILLS-mockup_1.png?v=1763018658&width=713	98%	500mcg	https://www.madebythrone.com/cdn/shop/files/Chromate_Job_29335.png	\N	2026-02-18 22:26:35+00	2026-02-18 22:26:35+00
1006	97	100	https://moglabs.bio/product/bpc-157/	https://moglabs.bio/wp-content/uploads/2025/09/bpc-1000x1000.png	\N	5mg	\N	\N	2026-02-18 22:26:35+00	2026-02-18 22:26:35+00
1007	97	186	https://moglabs.bio/product/bromantane/	https://moglabs.bio/wp-content/uploads/2026/02/broman-1000x1000.png	\N	500mcg	\N	\N	2026-02-18 22:28:25+00	2026-02-18 22:28:25+00
1011	96	26	https://arcanepeptides.com/product/cjc-1295/	https://arcanepeptides.com/wp-content/uploads/2025/09/cjcdac-1000x1000.png	\N	5mg	\N	\N	2026-02-18 22:33:54+00	2026-02-18 22:33:54+00
1012	93	26	https://ruo.bio/product/cjc-1295/	https://ruo.bio/wp-content/uploads/2025/12/dac5mg-1536x1536.png	98.341%	4.854mg	https://ruo.bio/wp-content/uploads/2025/12/Chromate_Job_30464.png	\N	2026-02-18 22:33:54+00	2026-02-18 22:33:54+00
1013	89	26	https://stratelabs.is/product/cjc-1295-dac/	https://stratelabs.is/wp-content/uploads/2024/11/CJC-1295-DAC.png	99%	2mg	\N	\N	2026-02-18 22:33:54+00	2026-02-18 22:33:54+00
1014	97	26	https://moglabs.bio/product/cjc-1295/	https://moglabs.bio/wp-content/uploads/2025/09/cjcdac-1-1000x1000.png	\N	5mg	\N	\N	2026-02-18 22:33:54+00	2026-02-18 22:33:54+00
1015	96	120	https://arcanepeptides.com/product/cjc-1295/	https://arcanepeptides.com/wp-content/uploads/2025/09/cjcnodac-1000x1000.png	\N	5mg	\N	\N	2026-02-18 22:34:16+00	2026-02-18 22:34:16+00
1016	93	120	https://ruo.bio/product/cjc-1295/	https://ruo.bio/wp-content/uploads/2025/12/nodac5mg-1536x1536.png	98.341%	4.854mg	https://ruo.bio/wp-content/uploads/2025/12/Chromate_Job_30464.png	\N	2026-02-18 22:34:16+00	2026-02-18 22:34:16+00
1017	89	120	https://stratelabs.is/product/cjc-1295/	https://stratelabs.is/wp-content/uploads/2024/11/CJC-1295.png	99.31%	2.53mg	https://stratelabs.is/wp-content/uploads/2023/01/Test-Report-74885-1.png	\N	2026-02-18 22:34:16+00	2026-02-18 22:34:16+00
1018	97	120	https://moglabs.bio/product/cjc-1295/	https://moglabs.bio/wp-content/uploads/2025/09/cjcnodac-1000x1000.png	\N	5mg	\N	\N	2026-02-18 22:34:16+00	2026-02-18 22:34:16+00
1019	93	105	https://ruo.bio/product/dihexa-5mg-30-units/	https://ruo.bio/wp-content/uploads/2025/12/Render_Mockup_4000_4000_2025-12-23-1536x1536.png	\N	5mg	\N	\N	2026-02-18 22:35:08+00	2026-02-18 22:35:08+00
1020	97	105	https://moglabs.bio/product/dihexa-5mg-30-units/	https://moglabs.bio/wp-content/uploads/2026/02/dihexa1-1000x1000.png	\N	5mg	\N	\N	2026-02-18 22:35:08+00	2026-02-18 22:35:08+00
1021	96	27	https://arcanepeptides.com/product/dsip/	https://arcanepeptides.com/wp-content/uploads/2025/09/dsip-1000x1000.png	\N	5mg	\N	\N	2026-02-18 22:36:07+00	2026-02-18 22:36:07+00
1022	93	27	https://ruo.bio/product/dsip-5mg/	https://ruo.bio/wp-content/uploads/2025/09/dsip-1-1536x1536.png	99.116%	5.06mg	https://ruo.bio/wp-content/uploads/2025/11/Test-Report-87533.png	\N	2026-02-18 22:36:07+00	2026-02-18 22:36:07+00
1023	89	27	https://stratelabs.is/?s=dsip&post_type=product&product_cat=0	https://stratelabs.is/wp-content/uploads/2024/11/DSIP-01.png	99.87%	10.45mg	https://stratelabs.is/wp-content/uploads/2025/07/Test-Report-74879.png	\N	2026-02-18 22:36:07+00	2026-02-18 22:36:07+00
1024	97	27	https://moglabs.bio/product/dsip-5mg/	https://moglabs.bio/wp-content/uploads/2025/09/dsip-2-1000x1000.png	99.116%	5.06mg	https://moglabs.bio/wp-content/uploads/2025/11/Test-Report-88318.png	\N	2026-02-18 22:36:07+00	2026-02-18 22:36:07+00
1025	96	104	https://arcanepeptides.com/product/ghk-cu/	https://arcanepeptides.com/wp-content/uploads/2025/09/ghk100-1-1000x1000.png	\N	100mg	\N	\N	2026-02-18 22:38:36+00	2026-02-18 22:38:36+00
1026	93	104	https://ruo.bio/product/ghk-cu/	https://ruo.bio/wp-content/uploads/2025/09/ghk100-1536x1536.png	99.879%	91.47mg	https://ruo.bio/wp-content/uploads/2025/10/Test-Report-88476.png	\N	2026-02-18 22:38:36+00	2026-02-18 22:38:36+00
1027	89	104	https://stratelabs.is/product/ghk-cu-50mg/	https://stratelabs.is/wp-content/uploads/2025/07/WhatsApp-Image-2025-07-13-at-12.27.49_a8be6871.jpg	99.97%	74mg	https://stratelabs.is/wp-content/uploads/2025/07/Test-Report-74865-1.png	\N	2026-02-18 22:38:36+00	2026-02-18 22:38:36+00
1028	95	104	https://www.madebythrone.com/products/new-ghk-cu	https://www.madebythrone.com/cdn/shop/files/NewProject_6.png?v=1753359036&width=493	99%	1mg	\N	\N	2026-02-18 22:38:36+00	2026-02-18 22:38:36+00
1029	97	104	https://moglabs.bio/product/ghk-cu/	https://moglabs.bio/wp-content/uploads/2025/09/ghk50-1-1000x1000.png	\N	50mg	\N	\N	2026-02-18 22:38:36+00	2026-02-18 22:38:36+00
1030	93	122	https://ruo.bio/product/ghrp-2-5mg/	https://ruo.bio/wp-content/uploads/2025/09/ghrp2-1536x1536.png	99.283%	4.79mg	https://ruo.bio/wp-content/uploads/2025/11/Test-Report-87509.png	\N	2026-02-18 22:39:09+00	2026-02-18 22:39:09+00
1031	89	122	https://stratelabs.is/product/ghrp-2-5mg/	https://stratelabs.is/wp-content/uploads/2024/11/GHRP-2-new-01.png	98.83%	4.88mg	https://stratelabs.is/wp-content/uploads/2021/07/GHRP2_2024Nov.png	\N	2026-02-18 22:39:09+00	2026-02-18 22:39:09+00
1032	97	122	https://moglabs.bio/product/ghrp-2-5mg/	https://moglabs.bio/wp-content/uploads/2025/09/ghrp2-1-1000x1000.png	\N	5mg	\N	\N	2026-02-18 22:39:09+00	2026-02-18 22:39:09+00
1033	93	121	https://ruo.bio/product/ghrp-6-5mg/	https://ruo.bio/wp-content/uploads/2025/09/ghrp6-1536x1536.png	99.476%	4.63mg	https://ruo.bio/wp-content/uploads/2025/11/Test-Report-87511.png	\N	2026-02-18 22:39:42+00	2026-02-18 22:39:42+00
1034	89	121	https://stratelabs.is/product/ghrp-6-5mg/	https://stratelabs.is/wp-content/uploads/2024/11/GHRP-6-new-01-1.png	99.98%	4.34mg	https://stratelabs.is/wp-content/uploads/2024/11/ghrp6.png	\N	2026-02-18 22:39:42+00	2026-02-18 22:39:42+00
1035	97	121	https://moglabs.bio/product/ghrp-6-5mg/	https://moglabs.bio/wp-content/uploads/2025/09/ghrp6-1-1000x1000.png	\N	5mg	\N	\N	2026-02-18 22:39:42+00	2026-02-18 22:39:42+00
1036	97	189	https://moglabs.bio/product/gw501516-10mg-60-units/	https://moglabs.bio/wp-content/uploads/2026/02/gw50151-1000x1000.png	\N	10mg	\N	\N	2026-02-18 22:40:14+00	2026-02-18 22:40:14+00
1037	96	19	https://arcanepeptides.com/product/hcg-5000iu/	https://arcanepeptides.com/wp-content/uploads/2025/09/hcg-1-1000x1000.png	\N	5000iu	\N	\N	2026-02-18 22:40:45+00	2026-02-18 22:40:45+00
1038	93	19	https://ruo.bio/product/hcg/	https://ruo.bio/wp-content/uploads/2025/09/hcg-1536x1536.png	\N	9529IU	https://ruo.bio/wp-content/uploads/2025/12/Chromate_Job_30428.png	\N	2026-02-18 22:40:45+00	2026-02-18 22:40:45+00
1039	89	19	https://stratelabs.is/product/hcg-5000iu/	https://stratelabs.is/wp-content/uploads/2021/07/85595a43-d30c-431b-8a22-bad55a1d27e3.jpeg	99%	5,000IU	\N	\N	2026-02-18 22:40:45+00	2026-02-18 22:40:45+00
1040	97	19	https://moglabs.bio/product/hcg-5000iu/	https://moglabs.bio/wp-content/uploads/2025/09/hcg-2-1000x1000.png	\N	5000iu	\N	\N	2026-02-18 22:40:45+00	2026-02-18 22:40:45+00
1041	93	173	https://ruo.bio/product/hexarelin/	https://ruo.bio/wp-content/uploads/2025/11/hexarelin-1536x1536.png	99.545%	4.87mg	https://ruo.bio/wp-content/uploads/2026/01/Test-Report-100907.png	\N	2026-02-18 22:41:16+00	2026-02-18 22:41:16+00
1042	97	173	https://moglabs.bio/product/hexarelin/	https://moglabs.bio/wp-content/uploads/2025/11/hexarelin-1-1000x1000.png	\N	5mg	\N	\N	2026-02-18 22:41:16+00	2026-02-18 22:41:16+00
1043	93	155	https://ruo.bio/product/hgh-frag-176-191-5mg/	https://ruo.bio/wp-content/uploads/2025/09/hghfrag-1536x1536.png	98.471%	5.343mg	https://ruo.bio/wp-content/uploads/2025/11/Chromate_Job_29075.png	\N	2026-02-18 22:42:10+00	2026-02-18 22:42:10+00
1044	89	155	https://stratelabs.is/product/hgh-frag-171-196-5mg/	https://stratelabs.is/wp-content/uploads/2022/12/HGH-FRAG-2ML.png	99.357%	5mg	https://stratelabs.is/wp-content/uploads/2022/12/Test-Report-74876.png	\N	2026-02-18 22:42:10+00	2026-02-18 22:42:10+00
1045	97	155	https://moglabs.bio/product/hgh-frag-176-191-5mg/	https://moglabs.bio/wp-content/uploads/2025/09/hghfrag-1-1000x1000.png	\N	5mg	\N	\N	2026-02-18 22:42:10+00	2026-02-18 22:42:10+00
1046	93	131	https://ruo.bio/product/hmg-75iu/	https://ruo.bio/wp-content/uploads/2025/09/hmg-1536x1536.png	\N	75IU	\N	\N	2026-02-18 22:42:40+00	2026-02-18 22:42:40+00
1047	89	131	https://stratelabs.is/product/hmg-75iu/	https://stratelabs.is/wp-content/uploads/2024/11/HMG.png	\N	75IU	\N	\N	2026-02-18 22:42:40+00	2026-02-18 22:42:40+00
1048	97	131	https://moglabs.bio/product/hmg-75iu/	https://moglabs.bio/wp-content/uploads/2025/09/hmg-1-1000x1000.png	\N	75iu	\N	\N	2026-02-18 22:42:40+00	2026-02-18 22:42:40+00
1049	93	128	https://ruo.bio/product/igf-1-des-1mg/	https://ruo.bio/wp-content/uploads/2025/09/igfdes-1536x1536.png	\N	1mg	\N	\N	2026-02-18 22:43:25+00	2026-02-18 22:43:25+00
1050	97	128	https://moglabs.bio/product/igf-1-des-1mg/	https://moglabs.bio/wp-content/uploads/2025/09/igfdes-1-1000x1000.png	\N	1mg	\N	\N	2026-02-18 22:43:25+00	2026-02-18 22:43:25+00
1051	96	112	https://arcanepeptides.com/product/igf-1-lr3/	https://arcanepeptides.com/wp-content/uploads/2025/09/igflr3-1000x1000.png	\N	1mg	\N	\N	2026-02-18 22:43:54+00	2026-02-18 22:43:54+00
1052	93	112	https://ruo.bio/product/igf-1-lr3/	https://ruo.bio/wp-content/uploads/2025/09/igf100mcg-1536x1536.png	99.201%	107.61mcg	https://ruo.bio/wp-content/uploads/2025/10/6KY9VJLM3T4SXPA81NFE.png	\N	2026-02-18 22:43:54+00	2026-02-18 22:43:54+00
1053	89	112	https://stratelabs.is/product/igf-1-lr3-1mg/	https://stratelabs.is/wp-content/uploads/2024/11/IGF-1-LR3.png	99.315%	1.13mg	https://stratelabs.is/wp-content/uploads/2023/01/Test-Report-74873.png	\N	2026-02-18 22:43:54+00	2026-02-18 22:43:54+00
1054	97	112	https://moglabs.bio/product/igf-1-lr3/	https://moglabs.bio/wp-content/uploads/2025/09/igf-1000x1000.png	\N	1mg	\N	\N	2026-02-18 22:43:54+00	2026-02-18 22:43:54+00
1055	96	25	https://arcanepeptides.com/product/ipamorelin-5mg/	https://arcanepeptides.com/wp-content/uploads/2025/09/IPAM-1-1000x1000.png	\N	5mg	\N	\N	2026-02-18 22:44:56+00	2026-02-18 22:44:56+00
1056	93	25	https://ruo.bio/product/ipamorelin-5mg/	https://ruo.bio/wp-content/uploads/2025/09/ipam-1536x1536.png	99.877%	5.07mg	https://ruo.bio/wp-content/uploads/2025/09/Test-Report-87531.png	\N	2026-02-18 22:44:56+00	2026-02-18 22:44:56+00
1057	89	25	https://stratelabs.is/product/ipamorelin-10mg/	https://stratelabs.is/wp-content/uploads/2025/08/Ipamorelin-10mg-2ML.png	99.935%	11.47mg	https://stratelabs.is/wp-content/uploads/2025/08/Test-Report-74872.png	\N	2026-02-18 22:44:56+00	2026-02-18 22:44:56+00
1058	97	25	https://moglabs.bio/product/ipamorelin-5mg/	https://moglabs.bio/wp-content/uploads/2025/09/ipamorelin-1000x1000.png	99.877%	5.07mg	https://moglabs.bio/wp-content/uploads/2025/09/Test-Report-88329-1.png	\N	2026-02-18 22:44:56+00	2026-02-18 22:44:56+00
1059	93	4	https://ruo.bio/product/kpv/	https://ruo.bio/wp-content/uploads/2025/09/kpv-1536x1536.png	99.883%	5.183mg	https://ruo.bio/wp-content/uploads/2026/01/Chromate_Job_30899.png	\N	2026-02-18 22:45:43+00	2026-02-18 22:45:43+00
1060	89	4	https://stratelabs.is/product/kpv-10mg/	https://stratelabs.is/wp-content/uploads/2025/08/KPV10MG2ML16x.png	\N	10mg	\N	\N	2026-02-18 22:45:43+00	2026-02-18 22:45:43+00
1061	97	4	https://moglabs.bio/product/kpv-5mg/	https://moglabs.bio/wp-content/uploads/2025/09/kpv-1-1000x1000.png	\N	5mg	\N	\N	2026-02-18 22:45:43+00	2026-02-18 22:45:43+00
1062	96	20	https://arcanepeptides.com/product/l-glutathione/	https://arcanepeptides.com/wp-content/uploads/2025/09/gluta-1000x1000.png	\N	1500mg	\N	\N	2026-02-18 22:46:25+00	2026-02-18 22:46:25+00
1063	93	20	https://ruo.bio/product/l-glutathione/	https://ruo.bio/wp-content/uploads/2025/09/gsh600-1536x1536.png	\N	529.1mg	https://ruo.bio/wp-content/uploads/2026/01/Chromate_Job_31353.png	\N	2026-02-18 22:46:25+00	2026-02-18 22:46:25+00
1064	89	20	https://stratelabs.is/product/l-gluthatione-200mg-ml/	https://stratelabs.is/wp-content/uploads/2024/11/GLUTATHIONE-new-01.png	98.8%	2,000mg	https://stratelabs.is/wp-content/uploads/2024/11/Screenshot-2024-07-26-125917.png	\N	2026-02-18 22:46:25+00	2026-02-18 22:46:25+00
1065	97	20	https://moglabs.bio/product/l-glutathione/	https://moglabs.bio/wp-content/uploads/2025/09/gluta-1000x1000.png	\N	1500mg	\N	\N	2026-02-18 22:46:25+00	2026-02-18 22:46:25+00
1066	96	180	https://arcanepeptides.com/product/melanotan-i-mt-1-10mg/	https://arcanepeptides.com/wp-content/uploads/2025/11/mt1-1-1000x1000.png	\N	10mg	\N	\N	2026-02-18 22:47:02+00	2026-02-18 22:47:02+00
1067	93	180	https://ruo.bio/product/melanotan-i-mt-1-10mg/	https://ruo.bio/wp-content/uploads/2025/11/mt1-1536x1536.png	99.386%	10.73mg	https://ruo.bio/wp-content/uploads/2025/11/Chromate_Job_29559.png	\N	2026-02-18 22:47:02+00	2026-02-18 22:47:02+00
1068	97	180	https://moglabs.bio/product/melanotan-i-mt-1-10mg/	https://moglabs.bio/wp-content/uploads/2025/11/mt1-1-1000x1000.png	\N	10mg	\N	\N	2026-02-18 22:47:02+00	2026-02-18 22:47:02+00
1069	96	3	https://arcanepeptides.com/product/melanotan-ii-mt-2-10mg/	https://arcanepeptides.com/wp-content/uploads/2025/09/mt2-1000x1000.png	\N	10mg	\N	\N	2026-02-18 22:47:28+00	2026-02-18 22:47:28+00
1070	93	3	https://ruo.bio/product/melanotan-ii-mt-2-10mg/	https://ruo.bio/wp-content/uploads/2025/09/mt-2-1536x1536.png	99.431%	10.90mg	https://ruo.bio/wp-content/uploads/2025/10/Test-Report-83245.png	\N	2026-02-18 22:47:28+00	2026-02-18 22:47:28+00
1071	89	3	https://stratelabs.is/product/melanotan-2-10mg/	https://stratelabs.is/wp-content/uploads/2024/11/MT2-new-01.png	99.83%	11.45mg	https://stratelabs.is/wp-content/uploads/2021/07/Test-Report-68566.png	\N	2026-02-18 22:47:28+00	2026-02-18 22:47:28+00
1072	97	3	https://moglabs.bio/product/melanotan-ii-mt-2-10mg/	https://moglabs.bio/wp-content/uploads/2025/09/mt2-1-1000x1000.png	\N	10mg	\N	\N	2026-02-18 22:47:28+00	2026-02-18 22:47:28+00
1073	93	178	https://ruo.bio/product/methylene-blue-1-50ml/	https://ruo.bio/wp-content/uploads/2025/09/mblue2-1536x1536.png	100%	10mg/mL	\N	\N	2026-02-18 22:48:30+00	2026-02-18 22:48:30+00
1074	97	178	https://moglabs.bio/product/methylene-blue-1-50ml/	https://moglabs.bio/wp-content/uploads/2025/09/methyleneblue-1000x1000.png	100%	10mg/ml	\N	\N	2026-02-18 22:48:30+00	2026-02-18 22:48:30+00
1075	93	191	https://ruo.bio/product/mk677/	https://ruo.bio/wp-content/uploads/2026/01/Chromate_Job_31028.png	\N	32mg	https://ruo.bio/wp-content/uploads/2026/01/Chromate_Job_31028.png	\N	2026-02-18 22:49:04+00	2026-02-18 22:49:04+00
1076	97	191	https://moglabs.bio/product/mk-677-25mg-60-units/	https://moglabs.bio/wp-content/uploads/2026/02/mk6777-1000x1000.png	\N	25mg	\N	\N	2026-02-18 22:49:04+00	2026-02-18 22:49:04+00
1077	96	126	https://arcanepeptides.com/product/mots-c/	https://arcanepeptides.com/wp-content/uploads/2025/09/motsc-1000x1000.png	\N	10mg	\N	\N	2026-02-18 22:49:33+00	2026-02-18 22:49:33+00
1078	93	126	https://ruo.bio/product/mots-c/	https://ruo.bio/wp-content/uploads/2025/09/mots-1536x1536.png	99.565%	43.09mg	https://ruo.bio/wp-content/uploads/2025/10/Chromate_Job_29874.png	\N	2026-02-18 22:49:33+00	2026-02-18 22:49:33+00
1079	89	126	https://stratelabs.is/product/mots-c-10mg/	https://stratelabs.is/wp-content/uploads/2024/11/MOS-C-01.png	99.771%	11.06mg	https://stratelabs.is/wp-content/uploads/2022/08/Test-Report-74880.png	\N	2026-02-18 22:49:33+00	2026-02-18 22:49:33+00
1080	97	126	https://moglabs.bio/product/mots-c/	https://moglabs.bio/wp-content/uploads/2025/09/mots-1-1000x1000.png	\N	10mg	\N	\N	2026-02-18 22:49:33+00	2026-02-18 22:49:33+00
1081	96	158	https://arcanepeptides.com/product/nad-500mg/	https://arcanepeptides.com/wp-content/uploads/2025/09/nad-1000x1000.png	\N	500mg	\N	\N	2026-02-18 22:50:10+00	2026-02-18 22:50:10+00
1082	93	158	https://ruo.bio/product/nad-500mg/	https://ruo.bio/wp-content/uploads/2025/09/nad-1-1536x1536.png	\N	477.78mg	https://ruo.bio/wp-content/uploads/2025/10/J59823HBFPXQ07DVUWM4.png	\N	2026-02-18 22:50:10+00	2026-02-18 22:50:10+00
1083	89	158	https://stratelabs.is/product/nad/	https://stratelabs.is/wp-content/uploads/2025/05/NAD-50mg.png	\N	500mg	\N	\N	2026-02-18 22:50:10+00	2026-02-18 22:50:10+00
1084	97	158	https://moglabs.bio/product/nad-500mg/	https://moglabs.bio/wp-content/uploads/2025/09/nad-3-1000x1000.png	\N	500mg	\N	\N	2026-02-18 22:50:10+00	2026-02-18 22:50:10+00
1085	97	185	https://moglabs.bio/product/oxiracetam-500mg-60-units/	https://moglabs.bio/wp-content/uploads/2026/02/oxiracetam-1000x1000.png	\N	500mg	\N	\N	2026-02-18 22:50:44+00	2026-02-18 22:50:44+00
1086	93	18	https://ruo.bio/product/oxytocin-5mg/	https://ruo.bio/wp-content/uploads/2025/09/oxy-1536x1536.png	99.010%	4.38mg	https://ruo.bio/wp-content/uploads/2026/01/Test-Report-100911.png	\N	2026-02-18 22:51:11+00	2026-02-18 22:51:11+00
1087	97	18	https://moglabs.bio/product/oxytocin-5mg/	https://moglabs.bio/wp-content/uploads/2025/09/oxytocin-1-1000x1000.png	\N	5mg	\N	\N	2026-02-18 22:51:11+00	2026-02-18 22:51:11+00
1088	93	123	https://ruo.bio/product/peg-mgf-2mg/	https://ruo.bio/wp-content/uploads/2025/09/pegmgf-1536x1536.png	\N	2mg	\N	\N	2026-02-18 22:51:39+00	2026-02-18 22:51:39+00
1089	89	123	https://stratelabs.is/product/peg-mgf-2mg/	https://stratelabs.is/wp-content/uploads/2024/11/PEG-MGF.png	99.002%	1.8mg	https://stratelabs.is/wp-content/uploads/2023/01/Test-Report-74870.png	\N	2026-02-18 22:51:39+00	2026-02-18 22:51:39+00
1090	97	123	https://moglabs.bio/product/peg-mgf-2mg/	https://moglabs.bio/wp-content/uploads/2025/09/pegmgf-1-1000x1000.png	\N	2mg	\N	\N	2026-02-18 22:51:39+00	2026-02-18 22:51:39+00
1091	97	193	https://moglabs.bio/product/phenylpiracetam-100mg-60-units/	https://moglabs.bio/wp-content/uploads/2026/02/phenyl-1000x1000.png	\N	100mg	\N	\N	2026-02-18 22:52:05+00	2026-02-18 22:52:05+00
1092	93	22	https://ruo.bio/product/pt-141-10mg/	https://ruo.bio/wp-content/uploads/2025/09/pt141-1536x1536.png	99.892%	9.25mg	https://ruo.bio/wp-content/uploads/2025/11/Test-Report-87513.png	\N	2026-02-18 22:52:42+00	2026-02-18 22:52:42+00
1093	89	22	https://stratelabs.is/product/pt141-10mg/	https://stratelabs.is/wp-content/uploads/2024/11/PT141-1.png	99.937%	11.95mg	https://stratelabs.is/wp-content/uploads/2023/01/Test-Report-74869.png	\N	2026-02-18 22:52:42+00	2026-02-18 22:52:42+00
1094	97	22	https://moglabs.bio/product/pt-141-10mg/	https://moglabs.bio/wp-content/uploads/2025/09/pt141-1-1000x1000.png	\N	10mg	\N	\N	2026-02-18 22:52:42+00	2026-02-18 22:52:42+00
1095	96	202	https://arcanepeptides.com/product/ru58841/	https://arcanepeptides.com/wp-content/uploads/2025/10/ru58841-1-1000x1000.png	\N	5%	\N	\N	2026-02-18 22:53:19+00	2026-02-18 22:53:19+00
1096	93	202	https://ruo.bio/product/ru-58841-5-50mg-ml-30ml/	https://ruo.bio/wp-content/uploads/2025/10/50mlru-1536x1536.png	\N	6.252%	https://ruo.bio/wp-content/uploads/2025/11/Chromate_Job_29216.png	\N	2026-02-18 22:53:19+00	2026-02-18 22:53:19+00
1097	97	202	https://moglabs.bio/product/ru-58841-5-50mg-ml-30ml/	https://moglabs.bio/wp-content/uploads/2025/10/ru58841-1-1000x1000.png	\N	5%	\N	\N	2026-02-18 22:53:19+00	2026-02-18 22:53:19+00
1098	96	24	https://arcanepeptides.com/product/selank-5mg/	https://arcanepeptides.com/wp-content/uploads/2025/09/selank-1-1000x1000.png	\N	5mg	\N	\N	2026-02-18 22:53:50+00	2026-02-18 22:53:50+00
1099	93	24	https://ruo.bio/product/selank-5mg/	https://ruo.bio/wp-content/uploads/2025/09/selank-1536x1536.png	\N	5mg	https://ruo.bio/wp-content/uploads/2025/10/Test-Report-83267.png	\N	2026-02-18 22:53:50+00	2026-02-18 22:53:50+00
1100	89	24	https://stratelabs.is/product/selank-10mg/	https://stratelabs.is/wp-content/uploads/2024/11/SELANK.png	99.962%	11.49mg	https://stratelabs.is/wp-content/uploads/2023/01/Test-Report-74868-1.png	\N	2026-02-18 22:53:50+00	2026-02-18 22:53:50+00
1101	97	24	https://moglabs.bio/product/selank-5mg/	https://moglabs.bio/wp-content/uploads/2025/09/selank-2-1000x1000.png	\N	5mg	\N	\N	2026-02-18 22:53:50+00	2026-02-18 22:53:50+00
1102	96	21	https://arcanepeptides.com/product/semax/	https://arcanepeptides.com/wp-content/uploads/2026/02/semaxs-1000x1000.png	\N	5mg	\N	\N	2026-02-18 22:54:25+00	2026-02-18 22:54:25+00
1103	93	21	https://ruo.bio/product/semax-5mg/	https://ruo.bio/wp-content/uploads/2025/09/semax-1536x1536.png	\N	10mg	https://ruo.bio/wp-content/uploads/2025/10/Test-Report-83270.png	\N	2026-02-18 22:54:25+00	2026-02-18 22:54:25+00
1104	89	21	https://stratelabs.is/product/semax-30mg/	https://stratelabs.is/wp-content/uploads/2023/01/WhatsApp-Image-2025-11-27-at-09.23.00_eebb9631.jpg	\N	10mg	\N	\N	2026-02-18 22:54:25+00	2026-02-18 22:54:25+00
1105	97	21	https://moglabs.bio/product/semax-5mg/	https://moglabs.bio/wp-content/uploads/2025/09/semax-1-1000x1000.png	\N	5mg	\N	\N	2026-02-18 22:54:25+00	2026-02-18 22:54:25+00
1106	96	2	https://arcanepeptides.com/product/tb-500/	https://arcanepeptides.com/wp-content/uploads/2025/09/tb500-1000x1000.png	\N	5mg	\N	\N	2026-02-18 22:54:56+00	2026-02-18 22:54:56+00
1107	93	2	https://ruo.bio/product/tb-500/	https://ruo.bio/wp-content/uploads/2025/09/tb5-1-1536x1536.png	99.876%	11.82mg	https://ruo.bio/wp-content/uploads/2025/09/Test-Report-87498.png	\N	2026-02-18 22:54:56+00	2026-02-18 22:54:56+00
1108	89	2	https://stratelabs.is/product/tb-500-2mg/	https://stratelabs.is/wp-content/uploads/2024/11/TB-500-new-01.png	99.005%	5.73mg	https://stratelabs.is/wp-content/uploads/2021/07/Test-Report-68567.png	\N	2026-02-18 22:54:56+00	2026-02-18 22:54:56+00
1109	97	2	https://moglabs.bio/product/tb-500/	https://moglabs.bio/wp-content/uploads/2025/09/tb500-1000x1000.png	\N	5mg	\N	\N	2026-02-18 22:54:56+00	2026-02-18 22:54:56+00
1110	96	102	https://arcanepeptides.com/product/tesamorelin/	https://arcanepeptides.com/wp-content/uploads/2025/11/tesa5-1000x1000.png	99.151%	4.63mg	https://arcanepeptides.com/wp-content/uploads/2026/01/Test-Report-101355-1.png	\N	2026-02-18 22:55:46+00	2026-02-18 22:55:46+00
1111	93	102	https://ruo.bio/product/tesamorelin/	https://ruo.bio/wp-content/uploads/2026/01/tesa1--1536x1536.png	99.151%	4.63mg	https://ruo.bio/wp-content/uploads/2026/01/Test-Report-100918.png	\N	2026-02-18 22:55:46+00	2026-02-18 22:55:46+00
1112	89	102	https://stratelabs.is/product/tesamorelin-10mg/	https://stratelabs.is/wp-content/uploads/2025/08/Tesanorelin-10mg-2ML.png	99.159%	10.04mg	https://stratelabs.is/wp-content/uploads/2025/08/Test-Report-74884.png	\N	2026-02-18 22:55:46+00	2026-02-18 22:55:46+00
1113	97	102	https://moglabs.bio/product/tesamorelin/	https://moglabs.bio/wp-content/uploads/2025/11/tesa-1000x1000.png	\N	99.151%	https://moglabs.bio/wp-content/uploads/2026/02/Test-Report-101356.png	\N	2026-02-18 22:55:46+00	2026-02-18 22:55:46+00
1114	93	157	https://ruo.bio/product/vip/	https://ruo.bio/wp-content/uploads/2025/09/vip-1536x1536.png	99.022%	4.85mg	https://ruo.bio/wp-content/uploads/2025/11/Test-Report-87529.png	\N	2026-02-18 22:56:14+00	2026-02-18 22:56:14+00
1115	89	157	https://stratelabs.is/product/vip-10mg/	https://stratelabs.is/wp-content/uploads/2025/08/VIP10MG2ML16x.png	99.480%	11.12mg	https://stratelabs.is/wp-content/uploads/2025/08/Test-Report-74905-1.png	\N	2026-02-18 22:56:14+00	2026-02-18 22:56:14+00
1116	97	157	https://moglabs.bio/product/vip/	https://moglabs.bio/wp-content/uploads/2025/09/vip-2-1000x1000.png	\N	5mg	\N	\N	2026-02-18 22:56:14+00	2026-02-18 22:56:14+00
\.


--
-- Data for Name: vendors; Type: TABLE DATA; Schema: public; Owner: -
--

COPY public.vendors (id, name, slug, icon, company_description, affordability_rating, quality_rating, shipping_speed_rating, customer_service_rating, color_bg, color_text, promo_code_id, is_us_vendor, is_popular, deleted_at, created_at, updated_at) FROM stdin;
88	6.Bio	6-bio	Atom	\N	5.00	5.00	5.00	5.00	#E3F2FD	#0097A7	\N	f	f	\N	2025-08-05 04:20:25+00	2025-08-05 04:20:25+00
89	Strate Labs	strate-labs	FlaskConical	Strate Labs, established in 2013, specializes in research chemicals, including peptides, SARMs, inje	5.00	5.00	5.00	5.00	#E3F2FD	#1565C0	\N	f	f	\N	2025-08-05 04:28:20+00	2025-08-05 04:28:20+00
93	RUO.bio	ruo-bio	Brain	Ruo.bio is an innovative, technology-forward, AI-powered research chemical provider specializing in	5.00	5.00	5.00	5.00	#FFFFFF	#C62828	\N	f	f	\N	2025-09-23 01:02:07+00	2025-09-23 01:02:31+00
94	Bulkpeptides	bulkpeptides	Database	Specializing in providing peptides at wholesale prices.	5.00	5.00	5.00	5.00	#FFFFFF	#E65100	\N	f	f	\N	2025-09-23 01:03:56+00	2025-09-23 01:03:56+00
95	Throne	throne	Pipette	Throne is an innovative cosmetics company specializing in peptide-powered topical hair and skin care	5.00	5.00	5.00	5.00	#FFFFFF	#E65100	\N	f	f	\N	2025-09-27 05:29:40+00	2025-09-27 05:29:40+00
96	Arcane	arcane	Star	\N	5.00	5.00	5.00	5.00	#E3F2FD	#00796B	\N	f	f	\N	2026-02-05 19:17:47+00	2026-02-05 19:18:47+00
97	Moglabs	moglabs	Microscope	Mog Labs delivers high-grade research compounds and peptides engineered for precision.	5.00	5.00	5.00	5.00	#FFFFFF	#2E7D32	\N	f	f	\N	2026-02-18 22:16:43+00	2026-02-18 22:16:43+00
\.


--
-- Data for Name: wiki_copilot_settings; Type: TABLE DATA; Schema: public; Owner: -
--

COPY public.wiki_copilot_settings (key, value, updated_at, updated_by) FROM stdin;
\.


--
-- Data for Name: wiki_coupons; Type: TABLE DATA; Schema: public; Owner: -
--

COPY public.wiki_coupons (id, code, vendor_id, influencer_id, discount_type, discount_value, description, start_date, end_date, is_active, usage_count, max_usage, affiliate_url, deleted_at, created_at, updated_at) FROM stdin;
\.


--
-- Data for Name: wiki_influencer_analytics; Type: TABLE DATA; Schema: public; Owner: -
--

COPY public.wiki_influencer_analytics (id, user_id, page_views, clicks, clicks_vendors, created_at, updated_at) FROM stdin;
\.


--
-- Data for Name: wiki_peptide_analytics; Type: TABLE DATA; Schema: public; Owner: -
--

COPY public.wiki_peptide_analytics (id, ip_address, peptide_id, action, referer_url, user_agent, "timestamp") FROM stdin;
1	unknown	23	click	http://localhost:3001/	Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/605.1.15 (KHTML, like Gecko) Version/26.4 Safari/605.1.15	2026-04-23 01:40:58.673+00
2	unknown	23	view	http://localhost:3001/peptide/retatrutide	Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/605.1.15 (KHTML, like Gecko) Version/26.4 Safari/605.1.15	2026-04-23 01:40:59.847+00
3	unknown	23	view	http://localhost:3001/peptide/retatrutide	Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/605.1.15 (KHTML, like Gecko) Version/26.4 Safari/605.1.15	2026-04-23 01:40:59.847+00
4	unknown	23	click	http://localhost:3001/	Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/605.1.15 (KHTML, like Gecko) Version/26.4 Safari/605.1.15	2026-04-23 01:41:26.139+00
5	unknown	100	click	http://localhost:3001/	Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/605.1.15 (KHTML, like Gecko) Version/26.4 Safari/605.1.15	2026-04-23 01:47:24.988+00
6	unknown	100	view	http://localhost:3001/peptide/bpc-157	Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/605.1.15 (KHTML, like Gecko) Version/26.4 Safari/605.1.15	2026-04-23 01:47:26.455+00
7	unknown	100	view	http://localhost:3001/peptide/bpc-157	Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/605.1.15 (KHTML, like Gecko) Version/26.4 Safari/605.1.15	2026-04-23 01:47:26.455+00
8	unknown	113	view	http://localhost:3002/peptide/5-amino-1mq	Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/605.1.15 (KHTML, like Gecko) Version/26.4 Safari/605.1.15	2026-04-23 01:50:09.756+00
9	unknown	113	view	http://localhost:3002/peptide/5-amino-1mq	Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/605.1.15 (KHTML, like Gecko) Version/26.4 Safari/605.1.15	2026-04-23 01:50:09.821+00
10	unknown	113	view	http://localhost:3001/peptide/5-amino-1mq	Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/605.1.15 (KHTML, like Gecko) Version/26.4 Safari/605.1.15	2026-04-23 01:50:21.883+00
11	unknown	113	view	http://localhost:3001/peptide/5-amino-1mq	Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/605.1.15 (KHTML, like Gecko) Version/26.4 Safari/605.1.15	2026-04-23 01:50:21.884+00
12	unknown	100	click	http://localhost:3002/	Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/605.1.15 (KHTML, like Gecko) Version/26.4 Safari/605.1.15	2026-04-23 02:06:49.909+00
13	unknown	100	view	http://localhost:3002/peptide/bpc-157	Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/605.1.15 (KHTML, like Gecko) Version/26.4 Safari/605.1.15	2026-04-23 02:06:50.632+00
14	unknown	100	view	http://localhost:3002/peptide/bpc-157	Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/605.1.15 (KHTML, like Gecko) Version/26.4 Safari/605.1.15	2026-04-23 02:06:50.631+00
15	unknown	23	click	http://localhost:3001/	Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/605.1.15 (KHTML, like Gecko) Version/26.4 Safari/605.1.15	2026-04-23 02:09:47.721+00
16	unknown	100	click	http://localhost:3001/	Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/605.1.15 (KHTML, like Gecko) Version/26.4 Safari/605.1.15	2026-04-23 02:14:43.65+00
17	unknown	20	view	http://localhost:3001/peptide/glutathione	Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/605.1.15 (KHTML, like Gecko) Version/26.4 Safari/605.1.15	2026-04-23 02:15:00.299+00
18	unknown	20	view	http://localhost:3001/peptide/glutathione	Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/605.1.15 (KHTML, like Gecko) Version/26.4 Safari/605.1.15	2026-04-23 02:15:00.32+00
19	unknown	23	click	http://localhost:3001/	Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/605.1.15 (KHTML, like Gecko) Version/26.4 Safari/605.1.15	2026-04-23 02:18:12.511+00
20	unknown	117	view	http://localhost:3001/peptide/ace-031	Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/605.1.15 (KHTML, like Gecko) Version/26.4 Safari/605.1.15	2026-04-23 02:28:52.087+00
21	unknown	117	view	http://localhost:3001/peptide/ace-031	Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/605.1.15 (KHTML, like Gecko) Version/26.4 Safari/605.1.15	2026-04-23 02:28:52.089+00
22	unknown	23	click	http://localhost:3001/	Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/605.1.15 (KHTML, like Gecko) Version/26.4 Safari/605.1.15	2026-04-23 03:53:17.231+00
23	unknown	23	view	http://localhost:3001/peptide/retatrutide	Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/605.1.15 (KHTML, like Gecko) Version/26.4 Safari/605.1.15	2026-04-23 03:53:17.819+00
24	unknown	23	view	http://localhost:3001/peptide/retatrutide	Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/605.1.15 (KHTML, like Gecko) Version/26.4 Safari/605.1.15	2026-04-23 03:53:17.82+00
25	unknown	216	view	http://localhost:3001/peptide/ahk-cu	Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/605.1.15 (KHTML, like Gecko) Version/26.4 Safari/605.1.15	2026-04-23 04:02:11.455+00
26	unknown	216	view	http://localhost:3001/peptide/ahk-cu	Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/605.1.15 (KHTML, like Gecko) Version/26.4 Safari/605.1.15	2026-04-23 04:02:11.532+00
27	unknown	25	click	http://localhost:3001/	Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/605.1.15 (KHTML, like Gecko) Version/26.4 Safari/605.1.15	2026-04-23 04:11:58.063+00
28	unknown	25	view	http://localhost:3001/peptide/ipamorelin	Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/605.1.15 (KHTML, like Gecko) Version/26.4 Safari/605.1.15	2026-04-23 04:11:58.875+00
29	unknown	25	view	http://localhost:3001/peptide/ipamorelin	Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/605.1.15 (KHTML, like Gecko) Version/26.4 Safari/605.1.15	2026-04-23 04:11:58.876+00
30	unknown	104	click	http://localhost:3001/	Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/605.1.15 (KHTML, like Gecko) Version/26.4 Safari/605.1.15	2026-04-23 04:12:14.047+00
31	unknown	104	view	http://localhost:3001/peptide/ghk-cu	Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/605.1.15 (KHTML, like Gecko) Version/26.4 Safari/605.1.15	2026-04-23 04:12:14.92+00
32	unknown	104	view	http://localhost:3001/peptide/ghk-cu	Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/605.1.15 (KHTML, like Gecko) Version/26.4 Safari/605.1.15	2026-04-23 04:12:14.919+00
33	unknown	104	click	http://localhost:3001/	Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/605.1.15 (KHTML, like Gecko) Version/26.4 Safari/605.1.15	2026-04-23 04:13:47.149+00
34	unknown	104	click	http://localhost:3001/	Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/605.1.15 (KHTML, like Gecko) Version/26.4 Safari/605.1.15	2026-04-23 04:20:49.785+00
35	unknown	23	click	http://localhost:3001/	Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/605.1.15 (KHTML, like Gecko) Version/26.4 Safari/605.1.15	2026-04-23 04:35:39.905+00
36	unknown	23	view	http://localhost:3002/peptide/retatrutide	Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/147.0.0.0 Safari/537.36	2026-04-23 04:39:59.598+00
37	unknown	23	view	http://localhost:3002/peptide/retatrutide	Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/147.0.0.0 Safari/537.36	2026-04-23 04:39:59.599+00
38	unknown	23	click	http://localhost:3002/	Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/147.0.0.0 Safari/537.36	2026-04-23 04:40:27.498+00
39	unknown	23	click	http://localhost:3001/	Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/605.1.15 (KHTML, like Gecko) Version/26.4 Safari/605.1.15	2026-04-23 04:45:25.268+00
40	unknown	23	click	http://localhost:3002/	Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/147.0.0.0 Safari/537.36	2026-04-23 04:52:09.838+00
41	unknown	25	click	http://localhost:3002/	Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/147.0.0.0 Safari/537.36	2026-04-23 04:52:22.994+00
42	unknown	25	view	http://localhost:3002/peptide/ipamorelin	Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/147.0.0.0 Safari/537.36	2026-04-23 04:52:23.801+00
43	unknown	25	view	http://localhost:3002/peptide/ipamorelin	Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/147.0.0.0 Safari/537.36	2026-04-23 04:52:23.802+00
44	unknown	23	click	http://localhost:3002/	Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/147.0.0.0 Safari/537.36	2026-04-23 05:00:08.886+00
45	unknown	104	click	http://localhost:3001/	Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/605.1.15 (KHTML, like Gecko) Version/26.4 Safari/605.1.15	2026-04-23 05:00:38.875+00
46	unknown	100	click	http://localhost:3001/	Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/605.1.15 (KHTML, like Gecko) Version/26.4 Safari/605.1.15	2026-04-23 05:02:48.241+00
47	unknown	100	view	http://localhost:3001/peptide/bpc-157	Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/605.1.15 (KHTML, like Gecko) Version/26.4 Safari/605.1.15	2026-04-23 05:02:48.949+00
48	unknown	100	view	http://localhost:3001/peptide/bpc-157	Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/605.1.15 (KHTML, like Gecko) Version/26.4 Safari/605.1.15	2026-04-23 05:02:48.95+00
49	71.80.228.98, 157.52.96.137	23	click	http://localhost:3002/	Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/605.1.15 (KHTML, like Gecko) Version/26.4 Safari/605.1.15	2026-04-23 13:03:59.232+00
50	71.80.228.98, 157.52.96.137	23	view	http://localhost:3002/peptide/retatrutide	Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/605.1.15 (KHTML, like Gecko) Version/26.4 Safari/605.1.15	2026-04-23 13:04:01.218+00
51	71.80.228.98, 157.52.96.137	23	view	http://localhost:3002/peptide/retatrutide	Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/605.1.15 (KHTML, like Gecko) Version/26.4 Safari/605.1.15	2026-04-23 13:04:01.221+00
52	71.80.228.98, 157.52.96.137	113	view	http://localhost:3002/peptide/5-amino-1mq	Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/605.1.15 (KHTML, like Gecko) Version/26.4 Safari/605.1.15	2026-04-23 13:08:50.949+00
53	71.80.228.98, 157.52.96.137	113	view	http://localhost:3002/peptide/5-amino-1mq	Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/605.1.15 (KHTML, like Gecko) Version/26.4 Safari/605.1.15	2026-04-23 13:08:50.961+00
54	71.80.228.98, 157.52.96.137	25	view	http://localhost:3001/peptide/ipamorelin	Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/605.1.15 (KHTML, like Gecko) Version/26.4 Safari/605.1.15	2026-04-23 13:19:02.796+00
55	unknown	23	click	http://localhost:3001/	Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/605.1.15 (KHTML, like Gecko) Version/26.4 Safari/605.1.15	2026-04-23 13:45:50.184+00
56	unknown	23	view	http://localhost:3001/peptide/retatrutide	Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/605.1.15 (KHTML, like Gecko) Version/26.4 Safari/605.1.15	2026-04-23 13:45:51.162+00
57	unknown	23	view	http://localhost:3001/peptide/retatrutide	Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/605.1.15 (KHTML, like Gecko) Version/26.4 Safari/605.1.15	2026-04-23 13:45:51.163+00
58	unknown	104	click	http://localhost:3001/	Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/605.1.15 (KHTML, like Gecko) Version/26.4 Safari/605.1.15	2026-04-23 14:11:54.713+00
59	unknown	104	view	http://localhost:3001/peptide/ghk-cu	Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/605.1.15 (KHTML, like Gecko) Version/26.4 Safari/605.1.15	2026-04-23 14:11:55.496+00
60	unknown	104	view	http://localhost:3001/peptide/ghk-cu	Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/605.1.15 (KHTML, like Gecko) Version/26.4 Safari/605.1.15	2026-04-23 14:11:55.496+00
61	unknown	113	click	http://localhost:3001/	Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/605.1.15 (KHTML, like Gecko) Version/26.4 Safari/605.1.15	2026-04-23 14:33:59.077+00
62	unknown	113	view	http://localhost:3001/peptide/5-amino-1mq	Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/605.1.15 (KHTML, like Gecko) Version/26.4 Safari/605.1.15	2026-04-23 14:34:00.158+00
63	unknown	113	view	http://localhost:3001/peptide/5-amino-1mq	Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/605.1.15 (KHTML, like Gecko) Version/26.4 Safari/605.1.15	2026-04-23 14:34:00.158+00
64	unknown	104	click	http://localhost:3001/	Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/605.1.15 (KHTML, like Gecko) Version/26.4 Safari/605.1.15	2026-04-23 14:49:52.925+00
65	unknown	23	click	http://localhost:3001/	Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/605.1.15 (KHTML, like Gecko) Version/26.4 Safari/605.1.15	2026-04-23 14:52:18.185+00
66	unknown	23	click	http://localhost:3001/	Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/605.1.15 (KHTML, like Gecko) Version/26.4 Safari/605.1.15	2026-04-23 15:04:04.991+00
67	unknown	23	click	http://localhost:3001/	Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/605.1.15 (KHTML, like Gecko) Version/26.4 Safari/605.1.15	2026-04-23 15:19:25.779+00
68	unknown	23	click	http://localhost:3001/	Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/605.1.15 (KHTML, like Gecko) Version/26.4 Safari/605.1.15	2026-04-23 15:36:32.405+00
69	unknown	23	view	http://localhost:3001/peptide/retatrutide	Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/605.1.15 (KHTML, like Gecko) Version/26.4 Safari/605.1.15	2026-04-23 15:36:33.047+00
70	unknown	23	view	http://localhost:3001/peptide/retatrutide	Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/605.1.15 (KHTML, like Gecko) Version/26.4 Safari/605.1.15	2026-04-23 15:36:33.047+00
71	unknown	23	click	http://localhost:3001/	Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/605.1.15 (KHTML, like Gecko) Version/26.4 Safari/605.1.15	2026-04-23 15:38:13.667+00
72	174.208.165.76, 157.52.96.38	100	click	https://wiki-app-production-0c22.up.railway.app/	Mozilla/5.0 (iPhone; CPU iPhone OS 18_7 like Mac OS X) AppleWebKit/605.1.15 (KHTML, like Gecko) Version/26.3 Mobile/15E148 Safari/604.1	2026-04-23 15:54:54.234+00
73	174.208.165.76, 157.52.96.85	100	view	https://wiki-app-production-0c22.up.railway.app/peptide/bpc-157	Mozilla/5.0 (iPhone; CPU iPhone OS 18_7 like Mac OS X) AppleWebKit/605.1.15 (KHTML, like Gecko) Version/26.3 Mobile/15E148 Safari/604.1	2026-04-23 15:54:54.7+00
74	174.208.165.76, 157.52.96.68	25	click	https://wiki-app-production-0c22.up.railway.app/	Mozilla/5.0 (iPhone; CPU iPhone OS 18_7 like Mac OS X) AppleWebKit/605.1.15 (KHTML, like Gecko) Version/26.3 Mobile/15E148 Safari/604.1	2026-04-23 15:54:58.075+00
75	174.208.165.76, 157.52.96.68	25	view	https://wiki-app-production-0c22.up.railway.app/peptide/ipamorelin	Mozilla/5.0 (iPhone; CPU iPhone OS 18_7 like Mac OS X) AppleWebKit/605.1.15 (KHTML, like Gecko) Version/26.3 Mobile/15E148 Safari/604.1	2026-04-23 15:54:58.64+00
76	107.128.79.145, 140.248.88.43	23	click	https://wiki-app-production-0c22.up.railway.app/	Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/605.1.15 (KHTML, like Gecko) Version/26.4 Safari/605.1.15	2026-04-23 20:19:41.022+00
77	107.128.79.145, 140.248.88.43	23	view	https://wiki-app-production-0c22.up.railway.app/peptide/retatrutide	Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/605.1.15 (KHTML, like Gecko) Version/26.4 Safari/605.1.15	2026-04-23 20:19:41.285+00
78	174.208.160.39, 157.52.96.46	104	click	https://wiki-app-production-0c22.up.railway.app/	Mozilla/5.0 (iPhone; CPU iPhone OS 18_7 like Mac OS X) AppleWebKit/605.1.15 (KHTML, like Gecko) Version/26.3 Mobile/15E148 Safari/604.1	2026-04-24 03:49:53.436+00
79	174.208.160.39, 157.52.96.46	104	view	https://wiki-app-production-0c22.up.railway.app/peptide/ghk-cu	Mozilla/5.0 (iPhone; CPU iPhone OS 18_7 like Mac OS X) AppleWebKit/605.1.15 (KHTML, like Gecko) Version/26.3 Mobile/15E148 Safari/604.1	2026-04-24 03:49:54.035+00
80	73.164.174.14, 167.82.167.32	23	click	https://wiki-app-production-0c22.up.railway.app/	Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/147.0.0.0 Safari/537.36	2026-04-24 05:14:15.43+00
81	73.164.174.14, 167.82.167.32	23	view	https://wiki-app-production-0c22.up.railway.app/peptide/retatrutide	Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/147.0.0.0 Safari/537.36	2026-04-24 05:14:15.701+00
82	73.164.174.14, 167.82.167.32	190	view	https://wiki-app-production-0c22.up.railway.app/peptide/9-me-bc	Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/147.0.0.0 Safari/537.36	2026-04-24 05:16:18.666+00
83	73.164.174.14, 167.82.167.32	133	view	https://wiki-app-production-0c22.up.railway.app/peptide/aicar	Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/147.0.0.0 Safari/537.36	2026-04-24 05:16:45.969+00
84	73.164.174.14, 167.82.167.32	25	view	https://wiki-app-production-0c22.up.railway.app/peptide/ipamorelin	Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/147.0.0.0 Safari/537.36	2026-04-24 05:18:39.633+00
85	71.80.228.98, 157.52.96.88	205	view	http://localhost:3000/peptide/snap-8	Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/605.1.15 (KHTML, like Gecko) Version/26.4 Safari/605.1.15	2026-04-29 17:42:14.006+00
86	71.80.228.98, 157.52.96.88	205	view	http://localhost:3000/peptide/snap-8	Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/605.1.15 (KHTML, like Gecko) Version/26.4 Safari/605.1.15	2026-04-29 17:42:14.051+00
87	71.80.228.98, 157.52.96.88	117	view	http://localhost:3000/peptide/ace-031	Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/605.1.15 (KHTML, like Gecko) Version/26.4 Safari/605.1.15	2026-04-29 17:42:46.604+00
88	71.80.228.98, 157.52.96.88	117	view	http://localhost:3000/peptide/ace-031	Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/605.1.15 (KHTML, like Gecko) Version/26.4 Safari/605.1.15	2026-04-29 17:42:46.583+00
89	unknown	157	view	http://localhost:3001/peptide/vasoactive-intestinal-peptide	Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/605.1.15 (KHTML, like Gecko) Version/26.4 Safari/605.1.15	2026-05-01 21:20:41.79+00
90	unknown	157	view	http://localhost:3001/peptide/vasoactive-intestinal-peptide	Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/605.1.15 (KHTML, like Gecko) Version/26.4 Safari/605.1.15	2026-05-01 21:20:41.846+00
91	unknown	23	click	http://localhost:3002/	Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/605.1.15 (KHTML, like Gecko) Version/26.4 Safari/605.1.15	2026-05-01 21:23:22.15+00
92	unknown	23	view	http://localhost:3002/peptide/retatrutide	Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/605.1.15 (KHTML, like Gecko) Version/26.4 Safari/605.1.15	2026-05-01 21:24:10.17+00
93	unknown	100	click	http://localhost:3002/	Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/605.1.15 (KHTML, like Gecko) Version/26.4 Safari/605.1.15	2026-05-01 21:24:15.504+00
95	unknown	100	view	http://localhost:3002/peptide/bpc-157	Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/605.1.15 (KHTML, like Gecko) Version/26.4 Safari/605.1.15	2026-05-01 21:24:16.044+00
94	unknown	100	view	http://localhost:3002/peptide/bpc-157	Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/605.1.15 (KHTML, like Gecko) Version/26.4 Safari/605.1.15	2026-05-01 21:24:16.045+00
96	unknown	23	click	http://localhost:3002/	Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/605.1.15 (KHTML, like Gecko) Version/26.4 Safari/605.1.15	2026-05-01 22:48:25.051+00
97	unknown	23	view	http://localhost:3002/peptide/retatrutide	Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/605.1.15 (KHTML, like Gecko) Version/26.4 Safari/605.1.15	2026-05-01 22:48:26+00
98	unknown	23	view	http://localhost:3002/peptide/retatrutide	Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/605.1.15 (KHTML, like Gecko) Version/26.4 Safari/605.1.15	2026-05-01 22:48:26.001+00
99	unknown	23	click	http://localhost:3001/	Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/605.1.15 (KHTML, like Gecko) Version/26.4 Safari/605.1.15	2026-05-02 00:40:46.336+00
100	unknown	23	view	http://localhost:3001/peptide/retatrutide	Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/605.1.15 (KHTML, like Gecko) Version/26.4 Safari/605.1.15	2026-05-02 00:40:47.714+00
101	unknown	23	view	http://localhost:3001/peptide/retatrutide	Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/605.1.15 (KHTML, like Gecko) Version/26.4 Safari/605.1.15	2026-05-02 00:40:47.715+00
102	unknown	104	click	http://localhost:3001/	Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/605.1.15 (KHTML, like Gecko) Version/26.4 Safari/605.1.15	2026-05-02 00:49:37.089+00
103	unknown	104	view	http://localhost:3001/peptide/ghk-cu	Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/605.1.15 (KHTML, like Gecko) Version/26.4 Safari/605.1.15	2026-05-02 00:49:38.221+00
104	unknown	104	view	http://localhost:3001/peptide/ghk-cu	Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/605.1.15 (KHTML, like Gecko) Version/26.4 Safari/605.1.15	2026-05-02 00:49:38.221+00
\.


--
-- Data for Name: wiki_posts; Type: TABLE DATA; Schema: public; Owner: -
--

COPY public.wiki_posts (id, slug, title, content, author_name, status, published_at, categories, meta_title, meta_description, og_title, og_description, og_image, canonical_url, created_at, updated_at) FROM stdin;
1	test	Test	test	Carlos	published	2026-05-01 18:56:05.517+00	{peptides}	test	test	test	test	\N	\N	2026-05-01 18:56:05.517+00	2026-05-01 18:56:05.517+00
\.


--
-- Data for Name: wiki_referral_banners; Type: TABLE DATA; Schema: public; Owner: -
--

COPY public.wiki_referral_banners (id, user_id, title, description, theme_config, social_links_config, custom_url, avatar_url, is_active, sort_order, created_at, updated_at, avatar_type, avatar_icon) FROM stdin;
\.


--
-- Data for Name: wiki_referral_clicks; Type: TABLE DATA; Schema: public; Owner: -
--

COPY public.wiki_referral_clicks (id, referral_code, user_id, vendor_id, peptide_id, ip_address, user_agent, referer_url, action, tracking_id, social_source_url, "timestamp") FROM stdin;
\.


--
-- Data for Name: wiki_trending_peptides; Type: TABLE DATA; Schema: public; Owner: -
--

COPY public.wiki_trending_peptides (id, peptide_id, views, clicks, shares, created_at, updated_at) FROM stdin;
1	2	535	73	0	2025-04-15 02:28:26+00	2026-04-22 09:30:07+00
2	3	498	89	1	2025-04-15 02:28:26+00	2026-04-21 23:44:28+00
3	18	163	33	0	2025-04-15 02:28:26+00	2026-04-18 18:37:17+00
4	4	529	96	1	2025-04-15 02:28:26+00	2026-04-22 03:23:45+00
6	21	466	143	0	2025-04-15 02:28:26+00	2026-04-22 13:38:49+00
7	19	184	30	0	2025-04-15 02:28:26+00	2026-04-19 21:39:58+00
8	27	191	30	0	2025-04-15 02:28:26+00	2026-04-21 01:15:36+00
11	24	294	72	0	2025-04-15 02:28:26+00	2026-04-22 13:40:25+00
12	22	203	33	0	2025-04-15 02:28:26+00	2026-04-21 01:15:08+00
13	26	582	159	0	2025-04-15 02:28:26+00	2026-04-22 07:16:02+00
15	102	784	265	0	2025-08-07 18:47:56+00	2026-04-22 07:14:41+00
16	103	73	13	0	2025-08-07 19:43:56+00	2026-04-16 18:01:53+00
18	105	155	31	1	2025-08-08 00:31:12+00	2026-04-22 14:49:05+00
19	106	55	3	0	2025-08-08 00:57:08+00	2026-04-20 20:30:26+00
20	107	174	25	0	2025-08-08 05:39:00+00	2026-04-20 00:58:55+00
21	112	307	84	0	2025-08-13 12:47:13+00	2026-04-20 14:41:35+00
23	114	336	83	0	2025-08-14 23:16:30+00	2026-04-22 15:40:07+00
24	115	419	68	2	2025-08-20 15:43:19+00	2026-04-22 14:53:42+00
25	118	73	5	0	2025-08-21 01:49:03+00	2026-04-20 20:30:39+00
27	130	187	30	0	2025-08-27 03:29:44+00	2026-04-22 14:21:15+00
28	132	87	1	0	2025-08-30 04:15:54+00	2026-04-19 06:10:43+00
29	123	53	7	0	2025-08-30 12:38:48+00	2026-04-14 20:35:27+00
31	128	119	17	0	2025-08-31 12:24:51+00	2026-04-22 07:12:17+00
32	141	109	16	0	2025-09-03 02:38:52+00	2026-04-19 07:43:34+00
33	156	290	13	0	2025-09-07 23:02:30+00	2026-04-21 17:50:47+00
34	153	46	0	0	2025-09-08 22:55:37+00	2026-04-17 03:26:49+00
35	131	52	5	0	2025-09-11 11:47:32+00	2026-04-14 12:34:15+00
36	151	34	1	0	2025-09-11 11:50:34+00	2026-04-14 03:39:18+00
37	125	75	0	0	2025-09-11 12:07:04+00	2026-04-22 15:30:42+00
38	148	67	2	0	2025-09-11 12:08:24+00	2026-04-20 20:28:19+00
39	121	66	11	0	2025-09-11 12:16:12+00	2026-04-22 11:13:23+00
40	160	9	0	0	2025-09-11 12:29:07+00	2026-03-10 22:19:06+00
41	137	119	6	0	2025-09-11 12:29:38+00	2026-04-20 20:29:41+00
42	158	533	165	0	2025-09-11 12:33:06+00	2026-04-22 15:00:24+00
43	120	411	88	0	2025-09-11 12:42:00+00	2026-04-21 15:08:57+00
44	143	8	0	0	2025-09-11 12:43:06+00	2026-03-19 20:35:21+00
45	155	337	88	0	2025-09-11 12:44:07+00	2026-04-20 10:27:48+00
47	139	19	3	0	2025-09-11 12:56:58+00	2026-03-12 20:22:31+00
48	142	20	1	0	2025-09-11 12:58:13+00	2026-03-11 01:13:39+00
49	146	11	0	0	2025-09-11 13:01:26+00	2026-04-11 17:20:47+00
50	145	22	0	0	2025-09-11 13:05:12+00	2026-03-20 06:15:50+00
51	135	72	22	0	2025-09-11 13:07:51+00	2026-04-19 07:42:40+00
52	150	13	1	0	2025-09-11 13:11:20+00	2026-03-17 19:40:30+00
53	149	8	1	0	2025-09-11 13:15:25+00	2026-04-04 17:56:14+00
54	138	37	7	0	2025-09-11 13:33:36+00	2026-04-18 16:41:40+00
55	144	13	0	0	2025-09-11 13:36:34+00	2026-03-11 00:03:20+00
56	122	65	4	0	2025-09-11 13:58:43+00	2026-04-22 11:13:41+00
57	152	8	0	0	2025-09-11 14:00:19+00	2026-03-11 04:06:41+00
58	136	20	3	0	2025-09-11 14:00:28+00	2026-04-16 16:43:25+00
59	147	9	0	0	2025-09-11 14:06:57+00	2026-04-03 21:55:22+00
60	124	96	19	0	2025-09-11 14:40:38+00	2026-04-20 14:38:22+00
61	127	31	1	0	2025-09-11 14:55:31+00	2026-04-16 16:42:10+00
62	159	6	0	0	2025-09-11 15:06:46+00	2026-03-22 04:48:18+00
63	140	20	2	0	2025-09-11 15:23:54+00	2026-03-12 20:22:44+00
64	134	320	65	0	2025-09-11 15:25:25+00	2026-04-21 18:14:52+00
65	129	32	2	0	2025-09-12 07:04:18+00	2026-04-22 14:21:47+00
66	126	849	250	1	2025-09-12 07:12:41+00	2026-04-22 17:08:27+00
67	116	65	10	0	2025-09-12 07:16:14+00	2026-04-20 01:51:33+00
68	119	38	4	0	2025-09-12 07:34:07+00	2026-03-09 13:50:59+00
69	163	6	0	0	2025-09-15 16:50:16+00	2026-04-12 10:21:03+00
70	170	22	0	0	2025-09-26 23:05:44+00	2026-03-27 01:27:08+00
71	165	15	1	0	2025-09-29 07:53:11+00	2026-03-11 06:58:02+00
72	173	39	3	1	2025-10-05 10:33:21+00	2026-04-18 12:16:47+00
73	171	90	13	0	2025-10-07 03:25:38+00	2026-04-13 02:15:16+00
74	172	53	1	0	2025-10-07 03:26:05+00	2026-04-17 03:30:53+00
75	178	178	96	0	2025-10-19 22:21:23+00	2026-04-21 21:19:27+00
76	177	33	0	0	2025-10-20 05:58:37+00	2026-04-20 14:37:56+00
77	174	143	4	0	2025-10-20 21:51:39+00	2026-04-21 07:06:16+00
78	175	48	2	0	2025-10-30 01:14:02+00	2026-04-18 14:43:09+00
79	176	17	1	0	2025-11-01 13:52:34+00	2026-03-11 20:58:28+00
80	168	13	0	0	2025-11-02 03:22:58+00	2026-03-10 21:38:08+00
81	184	33	1	0	2025-11-04 21:38:55+00	2026-04-14 05:10:35+00
82	183	35	1	0	2025-11-04 21:40:07+00	2026-04-15 12:16:00+00
83	181	119	24	0	2025-11-05 00:33:07+00	2026-04-18 18:02:47+00
84	186	109	13	0	2025-11-05 01:40:02+00	2026-04-21 20:34:59+00
85	185	108	3	0	2025-11-05 01:43:42+00	2026-04-21 17:47:12+00
86	182	106	19	0	2025-11-05 01:51:46+00	2026-04-22 14:13:48+00
87	169	14	0	0	2025-11-05 08:31:25+00	2026-04-11 17:18:43+00
88	188	7	0	0	2025-11-05 08:50:34+00	2026-03-12 16:37:08+00
89	180	174	31	0	2025-11-05 08:53:16+00	2026-04-22 11:33:14+00
90	187	45	5	0	2025-11-05 08:55:41+00	2026-04-14 05:10:47+00
91	167	8	0	0	2025-11-05 09:01:33+00	2026-03-30 07:28:01+00
92	166	8	0	0	2025-11-05 09:15:48+00	2026-04-22 06:18:39+00
93	164	6	0	0	2025-11-05 09:17:22+00	2026-03-10 17:04:08+00
94	162	22	1	0	2025-11-05 09:21:06+00	2026-04-05 21:57:40+00
95	161	9	0	0	2025-11-05 09:24:55+00	2026-03-11 03:29:42+00
96	191	352	29	0	2025-11-06 01:17:41+00	2026-04-22 14:32:39+00
98	189	69	2	0	2025-11-06 21:17:30+00	2026-04-15 02:47:43+00
99	194	104	9	0	2025-11-07 13:26:38+00	2026-04-21 20:16:00+00
100	195	6	1	0	2025-11-10 11:40:08+00	2026-03-12 12:47:07+00
101	198	50	0	0	2025-11-16 02:49:17+00	2026-04-20 20:30:09+00
102	196	79	0	0	2025-11-17 22:55:54+00	2026-04-21 23:21:55+00
103	197	18	0	0	2025-11-25 16:37:05+00	2026-04-21 19:12:05+00
104	193	26	1	0	2025-11-26 15:04:09+00	2026-04-15 12:17:04+00
105	199	7	0	0	2025-11-30 19:01:55+00	2026-03-18 01:38:52+00
106	200	46	7	0	2025-12-08 03:29:18+00	2026-04-07 00:39:06+00
107	202	34	4	0	2025-12-14 18:13:35+00	2026-04-21 00:17:08+00
108	207	30	1	0	2025-12-14 20:48:31+00	2026-04-17 23:10:41+00
109	204	129	10	0	2025-12-14 21:47:51+00	2026-04-21 19:20:18+00
110	206	239	43	0	2025-12-15 18:03:14+00	2026-04-21 19:37:00+00
111	208	209	46	0	2025-12-16 02:46:08+00	2026-04-22 14:53:13+00
112	201	31	0	0	2025-12-17 02:35:38+00	2026-04-20 14:39:08+00
113	210	24	1	0	2025-12-18 18:34:44+00	2026-04-14 16:55:32+00
114	211	10	0	0	2025-12-19 00:09:27+00	2026-03-26 00:37:37+00
115	213	162	63	0	2025-12-19 15:34:05+00	2026-04-22 15:15:58+00
116	209	66	6	0	2025-12-19 19:21:17+00	2026-04-04 12:31:28+00
118	214	35	0	0	2025-12-23 21:37:15+00	2026-04-06 05:17:39+00
119	212	11	0	0	2026-01-01 02:20:58+00	2026-04-11 23:58:58+00
120	192	10	0	0	2026-01-07 02:41:07+00	2026-04-15 12:16:58+00
9	20	531	75	0	2025-04-15 02:28:26+00	2026-04-22 03:25:14+00
26	117	104	1	0	2025-08-21 04:49:29+00	2026-04-21 15:06:19+00
117	205	69	22	0	2025-12-22 01:54:09+00	2026-04-18 18:58:47+00
97	190	137	9	0	2025-11-06 20:19:30+00	2026-04-19 01:52:12+00
30	133	129	11	0	2025-08-31 01:58:51+00	2026-04-21 20:55:49+00
10	25	1061	560	0	2025-04-15 02:28:26+00	2026-04-22 14:31:07+00
46	157	146	13	0	2025-09-11 12:44:42+00	2026-04-09 15:09:52+00
17	104	3708	2410	3	2025-08-07 21:04:11+00	2026-04-22 15:27:52+00
122	203	10	0	0	2026-01-18 18:05:32+00	2026-03-23 05:39:10+00
123	217	12	1	0	2026-01-23 12:16:57+00	2026-03-22 18:08:38+00
124	215	8	0	0	2026-01-24 08:55:48+00	2026-03-21 16:05:41+00
121	216	175	15	0	2026-01-17 13:28:16+00	2026-04-22 06:14:04+00
22	113	873	80	1	2025-08-14 22:20:05+00	2026-04-22 16:34:51+00
14	100	1876	976	1	2025-08-07 18:08:22+00	2026-04-22 13:42:37+00
5	23	4709	3384	6	2025-04-15 02:28:26+00	2026-04-22 19:24:29+00
\.


--
-- Data for Name: wiki_user_peptide_feedback_answers; Type: TABLE DATA; Schema: public; Owner: -
--

COPY public.wiki_user_peptide_feedback_answers (id, user_id, peptide_id, feedback_question_id, response, answered_at, was_helpful) FROM stdin;
1	6965740d-e92b-421a-af2d-cb81c24792b3	23	1	test	2026-04-23 04:45:35.957+00	t
2	6965740d-e92b-421a-af2d-cb81c24792b3	113	1	good test	2026-04-23 14:48:50.394+00	t
\.


--
-- Data for Name: wiki_user_peptide_question_answers; Type: TABLE DATA; Schema: public; Owner: -
--

COPY public.wiki_user_peptide_question_answers (id, user_id, peptide_id, question_id, option_id, answered_at) FROM stdin;
\.


--
-- Data for Name: wiki_user_profiles; Type: TABLE DATA; Schema: public; Owner: -
--

COPY public.wiki_user_profiles (id, user_id, bio, social_links, is_influencer, referral_code, profile_visibility, created_at, updated_at) FROM stdin;
3	6965740d-e92b-421a-af2d-cb81c24792b3	\N	\N	f	\N	public	2026-04-23 04:45:09.353032+00	2026-04-25 01:13:45.732+00
1	2e34bfb0-482d-48d8-94a7-9f464c0b1f60	\N	\N	t	\N	public	2026-04-23 01:28:32.58654+00	2026-05-04 16:55:05.724+00
\.


--
-- Name: administration_methods_id_seq; Type: SEQUENCE SET; Schema: public; Owner: -
--

SELECT pg_catalog.setval('public.administration_methods_id_seq', 5, false);


--
-- Name: app_analytics_id_seq; Type: SEQUENCE SET; Schema: public; Owner: -
--

SELECT pg_catalog.setval('public.app_analytics_id_seq', 1, false);


--
-- Name: application_places_id_seq; Type: SEQUENCE SET; Schema: public; Owner: -
--

SELECT pg_catalog.setval('public.application_places_id_seq', 1, false);


--
-- Name: benefits_id_seq; Type: SEQUENCE SET; Schema: public; Owner: -
--

SELECT pg_catalog.setval('public.benefits_id_seq', 1, false);


--
-- Name: calc_analytics_id_seq; Type: SEQUENCE SET; Schema: public; Owner: -
--

SELECT pg_catalog.setval('public.calc_analytics_id_seq', 1, false);


--
-- Name: calc_daily_stats_id_seq; Type: SEQUENCE SET; Schema: public; Owner: -
--

SELECT pg_catalog.setval('public.calc_daily_stats_id_seq', 1, false);


--
-- Name: calc_user_profiles_id_seq; Type: SEQUENCE SET; Schema: public; Owner: -
--

SELECT pg_catalog.setval('public.calc_user_profiles_id_seq', 38, true);


--
-- Name: calc_user_reviews_id_seq; Type: SEQUENCE SET; Schema: public; Owner: -
--

SELECT pg_catalog.setval('public.calc_user_reviews_id_seq', 1, false);


--
-- Name: categories_id_seq; Type: SEQUENCE SET; Schema: public; Owner: -
--

SELECT pg_catalog.setval('public.categories_id_seq', 106, false);


--
-- Name: citations_id_seq; Type: SEQUENCE SET; Schema: public; Owner: -
--

SELECT pg_catalog.setval('public.citations_id_seq', 1, false);


--
-- Name: dosages_id_seq; Type: SEQUENCE SET; Schema: public; Owner: -
--

SELECT pg_catalog.setval('public.dosages_id_seq', 260, false);


--
-- Name: feedback_questions_id_seq; Type: SEQUENCE SET; Schema: public; Owner: -
--

SELECT pg_catalog.setval('public.feedback_questions_id_seq', 9, true);


--
-- Name: influencer_profiles_id_seq; Type: SEQUENCE SET; Schema: public; Owner: -
--

SELECT pg_catalog.setval('public.influencer_profiles_id_seq', 1, true);


--
-- Name: pepti_price_analytics_id_seq; Type: SEQUENCE SET; Schema: public; Owner: -
--

SELECT pg_catalog.setval('public.pepti_price_analytics_id_seq', 1, false);


--
-- Name: pepti_price_daily_stats_id_seq; Type: SEQUENCE SET; Schema: public; Owner: -
--

SELECT pg_catalog.setval('public.pepti_price_daily_stats_id_seq', 1, false);


--
-- Name: pepti_price_newsletter_subscribers_id_seq; Type: SEQUENCE SET; Schema: public; Owner: -
--

SELECT pg_catalog.setval('public.pepti_price_newsletter_subscribers_id_seq', 1, false);


--
-- Name: pepti_price_notifications_id_seq; Type: SEQUENCE SET; Schema: public; Owner: -
--

SELECT pg_catalog.setval('public.pepti_price_notifications_id_seq', 1, false);


--
-- Name: pepti_price_price_history_id_seq; Type: SEQUENCE SET; Schema: public; Owner: -
--

SELECT pg_catalog.setval('public.pepti_price_price_history_id_seq', 1, false);


--
-- Name: pepti_price_promo_codes_id_seq; Type: SEQUENCE SET; Schema: public; Owner: -
--

SELECT pg_catalog.setval('public.pepti_price_promo_codes_id_seq', 1, false);


--
-- Name: pepti_price_vendor_pricing_id_seq; Type: SEQUENCE SET; Schema: public; Owner: -
--

SELECT pg_catalog.setval('public.pepti_price_vendor_pricing_id_seq', 1, false);


--
-- Name: pepti_price_watchlist_id_seq; Type: SEQUENCE SET; Schema: public; Owner: -
--

SELECT pg_catalog.setval('public.pepti_price_watchlist_id_seq', 1, false);


--
-- Name: peptide_benefits_id_seq; Type: SEQUENCE SET; Schema: public; Owner: -
--

SELECT pg_catalog.setval('public.peptide_benefits_id_seq', 1, false);


--
-- Name: peptide_interactions_id_seq; Type: SEQUENCE SET; Schema: public; Owner: -
--

SELECT pg_catalog.setval('public.peptide_interactions_id_seq', 1, false);


--
-- Name: peptide_protocol_reconstitution_steps_id_seq; Type: SEQUENCE SET; Schema: public; Owner: -
--

SELECT pg_catalog.setval('public.peptide_protocol_reconstitution_steps_id_seq', 1, false);


--
-- Name: peptide_protocols_id_seq; Type: SEQUENCE SET; Schema: public; Owner: -
--

SELECT pg_catalog.setval('public.peptide_protocols_id_seq', 1790, false);


--
-- Name: peptide_question_assignments_id_seq; Type: SEQUENCE SET; Schema: public; Owner: -
--

SELECT pg_catalog.setval('public.peptide_question_assignments_id_seq', 1, false);


--
-- Name: peptide_question_option_assignments_id_seq; Type: SEQUENCE SET; Schema: public; Owner: -
--

SELECT pg_catalog.setval('public.peptide_question_option_assignments_id_seq', 69, true);


--
-- Name: peptide_question_options_id_seq; Type: SEQUENCE SET; Schema: public; Owner: -
--

SELECT pg_catalog.setval('public.peptide_question_options_id_seq', 59, true);


--
-- Name: peptide_questions_id_seq; Type: SEQUENCE SET; Schema: public; Owner: -
--

SELECT pg_catalog.setval('public.peptide_questions_id_seq', 10, true);


--
-- Name: peptide_references_id_seq; Type: SEQUENCE SET; Schema: public; Owner: -
--

SELECT pg_catalog.setval('public.peptide_references_id_seq', 1, false);


--
-- Name: peptide_research_indication_studies_id_seq; Type: SEQUENCE SET; Schema: public; Owner: -
--

SELECT pg_catalog.setval('public.peptide_research_indication_studies_id_seq', 1, false);


--
-- Name: peptide_research_indications_id_seq; Type: SEQUENCE SET; Schema: public; Owner: -
--

SELECT pg_catalog.setval('public.peptide_research_indications_id_seq', 1, false);


--
-- Name: peptide_side_effects_id_seq; Type: SEQUENCE SET; Schema: public; Owner: -
--

SELECT pg_catalog.setval('public.peptide_side_effects_id_seq', 1, false);


--
-- Name: peptides_id_seq; Type: SEQUENCE SET; Schema: public; Owner: -
--

SELECT pg_catalog.setval('public.peptides_id_seq', 244, true);


--
-- Name: protocol_application_places_id_seq; Type: SEQUENCE SET; Schema: public; Owner: -
--

SELECT pg_catalog.setval('public.protocol_application_places_id_seq', 1, false);


--
-- Name: protocol_dosage_benefits_id_seq; Type: SEQUENCE SET; Schema: public; Owner: -
--

SELECT pg_catalog.setval('public.protocol_dosage_benefits_id_seq', 1, false);


--
-- Name: protocol_dosage_side_effects_id_seq; Type: SEQUENCE SET; Schema: public; Owner: -
--

SELECT pg_catalog.setval('public.protocol_dosage_side_effects_id_seq', 1, false);


--
-- Name: protocol_dosages_id_seq; Type: SEQUENCE SET; Schema: public; Owner: -
--

SELECT pg_catalog.setval('public.protocol_dosages_id_seq', 1, false);


--
-- Name: protocol_quality_indicators_id_seq; Type: SEQUENCE SET; Schema: public; Owner: -
--

SELECT pg_catalog.setval('public.protocol_quality_indicators_id_seq', 1, false);


--
-- Name: research_studies_id_seq; Type: SEQUENCE SET; Schema: public; Owner: -
--

SELECT pg_catalog.setval('public.research_studies_id_seq', 1, false);


--
-- Name: roles_id_seq; Type: SEQUENCE SET; Schema: public; Owner: -
--

SELECT pg_catalog.setval('public.roles_id_seq', 2, true);


--
-- Name: schedules_id_seq; Type: SEQUENCE SET; Schema: public; Owner: -
--

SELECT pg_catalog.setval('public.schedules_id_seq', 18, false);


--
-- Name: sds_analytics_id_seq; Type: SEQUENCE SET; Schema: public; Owner: -
--

SELECT pg_catalog.setval('public.sds_analytics_id_seq', 1, false);


--
-- Name: side_effects_id_seq; Type: SEQUENCE SET; Schema: public; Owner: -
--

SELECT pg_catalog.setval('public.side_effects_id_seq', 52, false);


--
-- Name: user_roles_id_seq; Type: SEQUENCE SET; Schema: public; Owner: -
--

SELECT pg_catalog.setval('public.user_roles_id_seq', 17, true);


--
-- Name: user_suggestions_id_seq; Type: SEQUENCE SET; Schema: public; Owner: -
--

SELECT pg_catalog.setval('public.user_suggestions_id_seq', 1, true);


--
-- Name: vendor_peptides_id_seq; Type: SEQUENCE SET; Schema: public; Owner: -
--

SELECT pg_catalog.setval('public.vendor_peptides_id_seq', 1, false);


--
-- Name: vendors_id_seq; Type: SEQUENCE SET; Schema: public; Owner: -
--

SELECT pg_catalog.setval('public.vendors_id_seq', 98, false);


--
-- Name: wiki_coupons_id_seq; Type: SEQUENCE SET; Schema: public; Owner: -
--

SELECT pg_catalog.setval('public.wiki_coupons_id_seq', 1, false);


--
-- Name: wiki_influencer_analytics_id_seq; Type: SEQUENCE SET; Schema: public; Owner: -
--

SELECT pg_catalog.setval('public.wiki_influencer_analytics_id_seq', 1, false);


--
-- Name: wiki_peptide_analytics_id_seq; Type: SEQUENCE SET; Schema: public; Owner: -
--

SELECT pg_catalog.setval('public.wiki_peptide_analytics_id_seq', 104, true);


--
-- Name: wiki_posts_id_seq; Type: SEQUENCE SET; Schema: public; Owner: -
--

SELECT pg_catalog.setval('public.wiki_posts_id_seq', 1, true);


--
-- Name: wiki_referral_banners_id_seq; Type: SEQUENCE SET; Schema: public; Owner: -
--

SELECT pg_catalog.setval('public.wiki_referral_banners_id_seq', 1, false);


--
-- Name: wiki_referral_clicks_id_seq; Type: SEQUENCE SET; Schema: public; Owner: -
--

SELECT pg_catalog.setval('public.wiki_referral_clicks_id_seq', 1, false);


--
-- Name: wiki_trending_peptides_id_seq; Type: SEQUENCE SET; Schema: public; Owner: -
--

SELECT pg_catalog.setval('public.wiki_trending_peptides_id_seq', 228, true);


--
-- Name: wiki_user_peptide_feedback_answers_id_seq; Type: SEQUENCE SET; Schema: public; Owner: -
--

SELECT pg_catalog.setval('public.wiki_user_peptide_feedback_answers_id_seq', 2, true);


--
-- Name: wiki_user_peptide_question_answers_id_seq; Type: SEQUENCE SET; Schema: public; Owner: -
--

SELECT pg_catalog.setval('public.wiki_user_peptide_question_answers_id_seq', 1, false);


--
-- Name: wiki_user_profiles_id_seq; Type: SEQUENCE SET; Schema: public; Owner: -
--

SELECT pg_catalog.setval('public.wiki_user_profiles_id_seq', 4, true);


--
-- Name: administration_methods administration_methods_name_unique; Type: CONSTRAINT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.administration_methods
    ADD CONSTRAINT administration_methods_name_unique UNIQUE (name);


--
-- Name: administration_methods administration_methods_pkey; Type: CONSTRAINT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.administration_methods
    ADD CONSTRAINT administration_methods_pkey PRIMARY KEY (id);


--
-- Name: app_analytics app_analytics_pkey; Type: CONSTRAINT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.app_analytics
    ADD CONSTRAINT app_analytics_pkey PRIMARY KEY (id);


--
-- Name: app_credit_costs app_credit_costs_pkey; Type: CONSTRAINT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.app_credit_costs
    ADD CONSTRAINT app_credit_costs_pkey PRIMARY KEY (id);


--
-- Name: app_sources app_sources_pkey; Type: CONSTRAINT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.app_sources
    ADD CONSTRAINT app_sources_pkey PRIMARY KEY (code);


--
-- Name: application_places application_places_name_unique; Type: CONSTRAINT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.application_places
    ADD CONSTRAINT application_places_name_unique UNIQUE (name);


--
-- Name: application_places application_places_pkey; Type: CONSTRAINT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.application_places
    ADD CONSTRAINT application_places_pkey PRIMARY KEY (id);


--
-- Name: benefits benefits_pkey; Type: CONSTRAINT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.benefits
    ADD CONSTRAINT benefits_pkey PRIMARY KEY (id);


--
-- Name: calc_analytics calc_analytics_pkey; Type: CONSTRAINT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.calc_analytics
    ADD CONSTRAINT calc_analytics_pkey PRIMARY KEY (id);


--
-- Name: calc_daily_stats calc_daily_stats_pkey; Type: CONSTRAINT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.calc_daily_stats
    ADD CONSTRAINT calc_daily_stats_pkey PRIMARY KEY (id);


--
-- Name: calc_notification_devices calc_notification_devices_pkey; Type: CONSTRAINT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.calc_notification_devices
    ADD CONSTRAINT calc_notification_devices_pkey PRIMARY KEY (id);


--
-- Name: calc_notifications calc_notifications_pkey; Type: CONSTRAINT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.calc_notifications
    ADD CONSTRAINT calc_notifications_pkey PRIMARY KEY (id);


--
-- Name: calc_promo_banners calc_promo_banners_pkey; Type: CONSTRAINT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.calc_promo_banners
    ADD CONSTRAINT calc_promo_banners_pkey PRIMARY KEY (id);


--
-- Name: calc_user_devices calc_user_devices_pkey; Type: CONSTRAINT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.calc_user_devices
    ADD CONSTRAINT calc_user_devices_pkey PRIMARY KEY (id);


--
-- Name: calc_user_profiles calc_user_profiles_pkey; Type: CONSTRAINT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.calc_user_profiles
    ADD CONSTRAINT calc_user_profiles_pkey PRIMARY KEY (id);


--
-- Name: calc_user_profiles calc_user_profiles_user_id_unique; Type: CONSTRAINT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.calc_user_profiles
    ADD CONSTRAINT calc_user_profiles_user_id_unique UNIQUE (user_id);


--
-- Name: calc_user_reviews calc_user_reviews_pkey; Type: CONSTRAINT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.calc_user_reviews
    ADD CONSTRAINT calc_user_reviews_pkey PRIMARY KEY (id);


--
-- Name: calc_vials calc_vials_pkey; Type: CONSTRAINT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.calc_vials
    ADD CONSTRAINT calc_vials_pkey PRIMARY KEY (id);


--
-- Name: categories categories_pkey; Type: CONSTRAINT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.categories
    ADD CONSTRAINT categories_pkey PRIMARY KEY (id);


--
-- Name: categories categories_slug_unique; Type: CONSTRAINT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.categories
    ADD CONSTRAINT categories_slug_unique UNIQUE (slug);


--
-- Name: citations citations_doi_unique; Type: CONSTRAINT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.citations
    ADD CONSTRAINT citations_doi_unique UNIQUE (doi);


--
-- Name: citations citations_pkey; Type: CONSTRAINT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.citations
    ADD CONSTRAINT citations_pkey PRIMARY KEY (id);


--
-- Name: credit_accounts credit_accounts_pkey; Type: CONSTRAINT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.credit_accounts
    ADD CONSTRAINT credit_accounts_pkey PRIMARY KEY (id);


--
-- Name: credit_accounts credit_accounts_user_id_key; Type: CONSTRAINT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.credit_accounts
    ADD CONSTRAINT credit_accounts_user_id_key UNIQUE (user_id);


--
-- Name: credit_packages credit_packages_pkey; Type: CONSTRAINT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.credit_packages
    ADD CONSTRAINT credit_packages_pkey PRIMARY KEY (id);


--
-- Name: credit_transactions credit_transactions_pkey; Type: CONSTRAINT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.credit_transactions
    ADD CONSTRAINT credit_transactions_pkey PRIMARY KEY (id);


--
-- Name: dosages dosages_pkey; Type: CONSTRAINT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.dosages
    ADD CONSTRAINT dosages_pkey PRIMARY KEY (id);


--
-- Name: feedback_questions feedback_questions_pkey; Type: CONSTRAINT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.feedback_questions
    ADD CONSTRAINT feedback_questions_pkey PRIMARY KEY (id);


--
-- Name: feedback_questions feedback_questions_question_code_unique; Type: CONSTRAINT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.feedback_questions
    ADD CONSTRAINT feedback_questions_question_code_unique UNIQUE (question_code);


--
-- Name: influencer_profiles influencer_profiles_pkey; Type: CONSTRAINT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.influencer_profiles
    ADD CONSTRAINT influencer_profiles_pkey PRIMARY KEY (id);


--
-- Name: influencer_profiles influencer_profiles_referral_code_unique; Type: CONSTRAINT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.influencer_profiles
    ADD CONSTRAINT influencer_profiles_referral_code_unique UNIQUE (referral_code);


--
-- Name: influencer_profiles influencer_profiles_user_id_unique; Type: CONSTRAINT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.influencer_profiles
    ADD CONSTRAINT influencer_profiles_user_id_unique UNIQUE (user_id);


--
-- Name: pepti_price_analytics pepti_price_analytics_pkey; Type: CONSTRAINT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.pepti_price_analytics
    ADD CONSTRAINT pepti_price_analytics_pkey PRIMARY KEY (id);


--
-- Name: pepti_price_daily_stats pepti_price_daily_stats_pkey; Type: CONSTRAINT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.pepti_price_daily_stats
    ADD CONSTRAINT pepti_price_daily_stats_pkey PRIMARY KEY (id);


--
-- Name: pepti_price_newsletter_subscribers pepti_price_newsletter_subscribers_pkey; Type: CONSTRAINT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.pepti_price_newsletter_subscribers
    ADD CONSTRAINT pepti_price_newsletter_subscribers_pkey PRIMARY KEY (id);


--
-- Name: pepti_price_newsletter_subscribers pepti_price_newsletter_subscribers_unsubscribe_token_unique; Type: CONSTRAINT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.pepti_price_newsletter_subscribers
    ADD CONSTRAINT pepti_price_newsletter_subscribers_unsubscribe_token_unique UNIQUE (unsubscribe_token);


--
-- Name: pepti_price_notifications pepti_price_notifications_pkey; Type: CONSTRAINT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.pepti_price_notifications
    ADD CONSTRAINT pepti_price_notifications_pkey PRIMARY KEY (id);


--
-- Name: pepti_price_price_history pepti_price_price_history_pkey; Type: CONSTRAINT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.pepti_price_price_history
    ADD CONSTRAINT pepti_price_price_history_pkey PRIMARY KEY (id);


--
-- Name: pepti_price_promo_codes pepti_price_promo_codes_code_unique; Type: CONSTRAINT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.pepti_price_promo_codes
    ADD CONSTRAINT pepti_price_promo_codes_code_unique UNIQUE (code);


--
-- Name: pepti_price_promo_codes pepti_price_promo_codes_pkey; Type: CONSTRAINT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.pepti_price_promo_codes
    ADD CONSTRAINT pepti_price_promo_codes_pkey PRIMARY KEY (id);


--
-- Name: pepti_price_vendor_pricing pepti_price_vendor_pricing_pkey; Type: CONSTRAINT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.pepti_price_vendor_pricing
    ADD CONSTRAINT pepti_price_vendor_pricing_pkey PRIMARY KEY (id);


--
-- Name: pepti_price_watchlist pepti_price_watchlist_pkey; Type: CONSTRAINT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.pepti_price_watchlist
    ADD CONSTRAINT pepti_price_watchlist_pkey PRIMARY KEY (id);


--
-- Name: peptide_benefits peptide_benefits_pkey; Type: CONSTRAINT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.peptide_benefits
    ADD CONSTRAINT peptide_benefits_pkey PRIMARY KEY (id);


--
-- Name: peptide_interactions peptide_interactions_pkey; Type: CONSTRAINT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.peptide_interactions
    ADD CONSTRAINT peptide_interactions_pkey PRIMARY KEY (id);


--
-- Name: peptide_protocol_reconstitution_steps peptide_protocol_reconstitution_steps_pkey; Type: CONSTRAINT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.peptide_protocol_reconstitution_steps
    ADD CONSTRAINT peptide_protocol_reconstitution_steps_pkey PRIMARY KEY (id);


--
-- Name: peptide_protocols peptide_protocols_pkey; Type: CONSTRAINT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.peptide_protocols
    ADD CONSTRAINT peptide_protocols_pkey PRIMARY KEY (id);


--
-- Name: peptide_question_assignments peptide_question_assignments_pkey; Type: CONSTRAINT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.peptide_question_assignments
    ADD CONSTRAINT peptide_question_assignments_pkey PRIMARY KEY (id);


--
-- Name: peptide_question_option_assignments peptide_question_option_assignments_pkey; Type: CONSTRAINT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.peptide_question_option_assignments
    ADD CONSTRAINT peptide_question_option_assignments_pkey PRIMARY KEY (id);


--
-- Name: peptide_question_options peptide_question_options_pkey; Type: CONSTRAINT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.peptide_question_options
    ADD CONSTRAINT peptide_question_options_pkey PRIMARY KEY (id);


--
-- Name: peptide_questions peptide_questions_pkey; Type: CONSTRAINT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.peptide_questions
    ADD CONSTRAINT peptide_questions_pkey PRIMARY KEY (id);


--
-- Name: peptide_references peptide_references_pkey; Type: CONSTRAINT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.peptide_references
    ADD CONSTRAINT peptide_references_pkey PRIMARY KEY (id);


--
-- Name: peptide_research_indication_studies peptide_research_indication_studies_pkey; Type: CONSTRAINT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.peptide_research_indication_studies
    ADD CONSTRAINT peptide_research_indication_studies_pkey PRIMARY KEY (id);


--
-- Name: peptide_research_indications peptide_research_indications_pkey; Type: CONSTRAINT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.peptide_research_indications
    ADD CONSTRAINT peptide_research_indications_pkey PRIMARY KEY (id);


--
-- Name: peptide_side_effects peptide_side_effects_pkey; Type: CONSTRAINT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.peptide_side_effects
    ADD CONSTRAINT peptide_side_effects_pkey PRIMARY KEY (id);


--
-- Name: peptides peptides_pkey; Type: CONSTRAINT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.peptides
    ADD CONSTRAINT peptides_pkey PRIMARY KEY (id);


--
-- Name: peptides peptides_slug_unique; Type: CONSTRAINT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.peptides
    ADD CONSTRAINT peptides_slug_unique UNIQUE (slug);


--
-- Name: protocol_application_places protocol_application_places_pkey; Type: CONSTRAINT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.protocol_application_places
    ADD CONSTRAINT protocol_application_places_pkey PRIMARY KEY (id);


--
-- Name: protocol_dosage_benefits protocol_dosage_benefits_pkey; Type: CONSTRAINT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.protocol_dosage_benefits
    ADD CONSTRAINT protocol_dosage_benefits_pkey PRIMARY KEY (id);


--
-- Name: protocol_dosage_side_effects protocol_dosage_side_effects_pkey; Type: CONSTRAINT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.protocol_dosage_side_effects
    ADD CONSTRAINT protocol_dosage_side_effects_pkey PRIMARY KEY (id);


--
-- Name: protocol_dosages protocol_dosages_pkey; Type: CONSTRAINT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.protocol_dosages
    ADD CONSTRAINT protocol_dosages_pkey PRIMARY KEY (id);


--
-- Name: protocol_quality_indicators protocol_quality_indicators_pkey; Type: CONSTRAINT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.protocol_quality_indicators
    ADD CONSTRAINT protocol_quality_indicators_pkey PRIMARY KEY (id);


--
-- Name: research_studies research_studies_pkey; Type: CONSTRAINT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.research_studies
    ADD CONSTRAINT research_studies_pkey PRIMARY KEY (id);


--
-- Name: roles roles_name_unique; Type: CONSTRAINT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.roles
    ADD CONSTRAINT roles_name_unique UNIQUE (name);


--
-- Name: roles roles_pkey; Type: CONSTRAINT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.roles
    ADD CONSTRAINT roles_pkey PRIMARY KEY (id);


--
-- Name: schedules schedules_pkey; Type: CONSTRAINT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.schedules
    ADD CONSTRAINT schedules_pkey PRIMARY KEY (id);


--
-- Name: sds_analytics sds_analytics_pkey; Type: CONSTRAINT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.sds_analytics
    ADD CONSTRAINT sds_analytics_pkey PRIMARY KEY (id);


--
-- Name: sds_batches sds_batches_pkey; Type: CONSTRAINT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.sds_batches
    ADD CONSTRAINT sds_batches_pkey PRIMARY KEY (id);


--
-- Name: sds_compounds sds_compounds_pkey; Type: CONSTRAINT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.sds_compounds
    ADD CONSTRAINT sds_compounds_pkey PRIMARY KEY (id);


--
-- Name: sds_compounds sds_compounds_pubchem_cid_unique; Type: CONSTRAINT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.sds_compounds
    ADD CONSTRAINT sds_compounds_pubchem_cid_unique UNIQUE (pubchem_cid);


--
-- Name: sds_documents sds_documents_pkey; Type: CONSTRAINT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.sds_documents
    ADD CONSTRAINT sds_documents_pkey PRIMARY KEY (id);


--
-- Name: sds_hazard_data sds_hazard_data_compound_id_unique; Type: CONSTRAINT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.sds_hazard_data
    ADD CONSTRAINT sds_hazard_data_compound_id_unique UNIQUE (compound_id);


--
-- Name: sds_hazard_data sds_hazard_data_pkey; Type: CONSTRAINT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.sds_hazard_data
    ADD CONSTRAINT sds_hazard_data_pkey PRIMARY KEY (id);


--
-- Name: sds_job_queue sds_job_queue_pkey; Type: CONSTRAINT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.sds_job_queue
    ADD CONSTRAINT sds_job_queue_pkey PRIMARY KEY (id);


--
-- Name: sds_pdf_templates sds_pdf_templates_pkey; Type: CONSTRAINT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.sds_pdf_templates
    ADD CONSTRAINT sds_pdf_templates_pkey PRIMARY KEY (id);


--
-- Name: sds_pinned_compounds sds_pinned_compounds_pkey; Type: CONSTRAINT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.sds_pinned_compounds
    ADD CONSTRAINT sds_pinned_compounds_pkey PRIMARY KEY (id);


--
-- Name: sds_sections sds_sections_compound_id_unique; Type: CONSTRAINT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.sds_sections
    ADD CONSTRAINT sds_sections_compound_id_unique UNIQUE (compound_id);


--
-- Name: sds_sections sds_sections_pkey; Type: CONSTRAINT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.sds_sections
    ADD CONSTRAINT sds_sections_pkey PRIMARY KEY (id);


--
-- Name: side_effects side_effects_pkey; Type: CONSTRAINT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.side_effects
    ADD CONSTRAINT side_effects_pkey PRIMARY KEY (id);


--
-- Name: stripe_customers stripe_customers_pkey; Type: CONSTRAINT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.stripe_customers
    ADD CONSTRAINT stripe_customers_pkey PRIMARY KEY (id);


--
-- Name: stripe_customers stripe_customers_stripe_customer_id_key; Type: CONSTRAINT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.stripe_customers
    ADD CONSTRAINT stripe_customers_stripe_customer_id_key UNIQUE (stripe_customer_id);


--
-- Name: stripe_customers stripe_customers_user_id_key; Type: CONSTRAINT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.stripe_customers
    ADD CONSTRAINT stripe_customers_user_id_key UNIQUE (user_id);


--
-- Name: subscription_events subscription_events_pkey; Type: CONSTRAINT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.subscription_events
    ADD CONSTRAINT subscription_events_pkey PRIMARY KEY (id);


--
-- Name: subscriptions subscriptions_pkey; Type: CONSTRAINT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.subscriptions
    ADD CONSTRAINT subscriptions_pkey PRIMARY KEY (id);


--
-- Name: user_roles user_roles_pkey; Type: CONSTRAINT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.user_roles
    ADD CONSTRAINT user_roles_pkey PRIMARY KEY (id);


--
-- Name: user_suggestions user_suggestions_pkey; Type: CONSTRAINT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.user_suggestions
    ADD CONSTRAINT user_suggestions_pkey PRIMARY KEY (id);


--
-- Name: users users_auth_user_id_unique; Type: CONSTRAINT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.users
    ADD CONSTRAINT users_auth_user_id_unique UNIQUE (auth_user_id);


--
-- Name: users users_email_unique; Type: CONSTRAINT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.users
    ADD CONSTRAINT users_email_unique UNIQUE (email);


--
-- Name: users users_pkey; Type: CONSTRAINT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.users
    ADD CONSTRAINT users_pkey PRIMARY KEY (id);


--
-- Name: vendor_peptides vendor_peptides_pkey; Type: CONSTRAINT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.vendor_peptides
    ADD CONSTRAINT vendor_peptides_pkey PRIMARY KEY (id);


--
-- Name: vendors vendors_pkey; Type: CONSTRAINT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.vendors
    ADD CONSTRAINT vendors_pkey PRIMARY KEY (id);


--
-- Name: vendors vendors_slug_unique; Type: CONSTRAINT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.vendors
    ADD CONSTRAINT vendors_slug_unique UNIQUE (slug);


--
-- Name: wiki_copilot_settings wiki_copilot_settings_pkey; Type: CONSTRAINT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.wiki_copilot_settings
    ADD CONSTRAINT wiki_copilot_settings_pkey PRIMARY KEY (key);


--
-- Name: wiki_coupons wiki_coupons_code_unique; Type: CONSTRAINT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.wiki_coupons
    ADD CONSTRAINT wiki_coupons_code_unique UNIQUE (code);


--
-- Name: wiki_coupons wiki_coupons_pkey; Type: CONSTRAINT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.wiki_coupons
    ADD CONSTRAINT wiki_coupons_pkey PRIMARY KEY (id);


--
-- Name: wiki_influencer_analytics wiki_influencer_analytics_pkey; Type: CONSTRAINT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.wiki_influencer_analytics
    ADD CONSTRAINT wiki_influencer_analytics_pkey PRIMARY KEY (id);


--
-- Name: wiki_influencer_analytics wiki_influencer_analytics_user_id_unique; Type: CONSTRAINT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.wiki_influencer_analytics
    ADD CONSTRAINT wiki_influencer_analytics_user_id_unique UNIQUE (user_id);


--
-- Name: wiki_peptide_analytics wiki_peptide_analytics_pkey; Type: CONSTRAINT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.wiki_peptide_analytics
    ADD CONSTRAINT wiki_peptide_analytics_pkey PRIMARY KEY (id);


--
-- Name: wiki_posts wiki_posts_pkey; Type: CONSTRAINT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.wiki_posts
    ADD CONSTRAINT wiki_posts_pkey PRIMARY KEY (id);


--
-- Name: wiki_referral_banners wiki_referral_banners_pkey; Type: CONSTRAINT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.wiki_referral_banners
    ADD CONSTRAINT wiki_referral_banners_pkey PRIMARY KEY (id);


--
-- Name: wiki_referral_clicks wiki_referral_clicks_pkey; Type: CONSTRAINT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.wiki_referral_clicks
    ADD CONSTRAINT wiki_referral_clicks_pkey PRIMARY KEY (id);


--
-- Name: wiki_trending_peptides wiki_trending_peptides_peptide_id_unique; Type: CONSTRAINT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.wiki_trending_peptides
    ADD CONSTRAINT wiki_trending_peptides_peptide_id_unique UNIQUE (peptide_id);


--
-- Name: wiki_trending_peptides wiki_trending_peptides_pkey; Type: CONSTRAINT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.wiki_trending_peptides
    ADD CONSTRAINT wiki_trending_peptides_pkey PRIMARY KEY (id);


--
-- Name: wiki_user_peptide_feedback_answers wiki_user_peptide_feedback_answers_pkey; Type: CONSTRAINT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.wiki_user_peptide_feedback_answers
    ADD CONSTRAINT wiki_user_peptide_feedback_answers_pkey PRIMARY KEY (id);


--
-- Name: wiki_user_peptide_question_answers wiki_user_peptide_question_answers_pkey; Type: CONSTRAINT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.wiki_user_peptide_question_answers
    ADD CONSTRAINT wiki_user_peptide_question_answers_pkey PRIMARY KEY (id);


--
-- Name: wiki_user_profiles wiki_user_profiles_pkey; Type: CONSTRAINT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.wiki_user_profiles
    ADD CONSTRAINT wiki_user_profiles_pkey PRIMARY KEY (id);


--
-- Name: wiki_user_profiles wiki_user_profiles_referral_code_unique; Type: CONSTRAINT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.wiki_user_profiles
    ADD CONSTRAINT wiki_user_profiles_referral_code_unique UNIQUE (referral_code);


--
-- Name: wiki_user_profiles wiki_user_profiles_user_id_unique; Type: CONSTRAINT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.wiki_user_profiles
    ADD CONSTRAINT wiki_user_profiles_user_id_unique UNIQUE (user_id);


--
-- Name: admin_methods_active_order_idx; Type: INDEX; Schema: public; Owner: -
--

CREATE INDEX admin_methods_active_order_idx ON public.administration_methods USING btree (is_active, sort_order);


--
-- Name: admin_methods_deleted_at_idx; Type: INDEX; Schema: public; Owner: -
--

CREATE INDEX admin_methods_deleted_at_idx ON public.administration_methods USING btree (deleted_at);


--
-- Name: admin_methods_name_unique_idx; Type: INDEX; Schema: public; Owner: -
--

CREATE UNIQUE INDEX admin_methods_name_unique_idx ON public.administration_methods USING btree (lower((name)::text));


--
-- Name: app_analytics_app_id_idx; Type: INDEX; Schema: public; Owner: -
--

CREATE INDEX app_analytics_app_id_idx ON public.app_analytics USING btree (app_id);


--
-- Name: app_analytics_app_id_timestamp_idx; Type: INDEX; Schema: public; Owner: -
--

CREATE INDEX app_analytics_app_id_timestamp_idx ON public.app_analytics USING btree (app_id, "timestamp");


--
-- Name: app_analytics_entity_idx; Type: INDEX; Schema: public; Owner: -
--

CREATE INDEX app_analytics_entity_idx ON public.app_analytics USING btree (entity_type, entity_id);


--
-- Name: app_analytics_event_type_idx; Type: INDEX; Schema: public; Owner: -
--

CREATE INDEX app_analytics_event_type_idx ON public.app_analytics USING btree (event_type);


--
-- Name: app_analytics_session_id_idx; Type: INDEX; Schema: public; Owner: -
--

CREATE INDEX app_analytics_session_id_idx ON public.app_analytics USING btree (session_id);


--
-- Name: app_analytics_timestamp_idx; Type: INDEX; Schema: public; Owner: -
--

CREATE INDEX app_analytics_timestamp_idx ON public.app_analytics USING btree ("timestamp");


--
-- Name: app_analytics_user_id_idx; Type: INDEX; Schema: public; Owner: -
--

CREATE INDEX app_analytics_user_id_idx ON public.app_analytics USING btree (user_id);


--
-- Name: app_credit_costs_active_idx; Type: INDEX; Schema: public; Owner: -
--

CREATE INDEX app_credit_costs_active_idx ON public.app_credit_costs USING btree (is_active);


--
-- Name: app_credit_costs_app_source_feature_key_idx; Type: INDEX; Schema: public; Owner: -
--

CREATE UNIQUE INDEX app_credit_costs_app_source_feature_key_idx ON public.app_credit_costs USING btree (app_source, feature_key);


--
-- Name: application_places_active_order_idx; Type: INDEX; Schema: public; Owner: -
--

CREATE INDEX application_places_active_order_idx ON public.application_places USING btree (is_active, sort_order);


--
-- Name: application_places_deleted_at_idx; Type: INDEX; Schema: public; Owner: -
--

CREATE INDEX application_places_deleted_at_idx ON public.application_places USING btree (deleted_at);


--
-- Name: application_places_name_idx; Type: INDEX; Schema: public; Owner: -
--

CREATE UNIQUE INDEX application_places_name_idx ON public.application_places USING btree (lower((name)::text));


--
-- Name: application_places_region_idx; Type: INDEX; Schema: public; Owner: -
--

CREATE INDEX application_places_region_idx ON public.application_places USING btree (anatomical_region);


--
-- Name: benefits_active_order_idx; Type: INDEX; Schema: public; Owner: -
--

CREATE INDEX benefits_active_order_idx ON public.benefits USING btree (is_active, sort_order);


--
-- Name: benefits_category_active_idx; Type: INDEX; Schema: public; Owner: -
--

CREATE INDEX benefits_category_active_idx ON public.benefits USING btree (category, is_active);


--
-- Name: benefits_category_idx; Type: INDEX; Schema: public; Owner: -
--

CREATE INDEX benefits_category_idx ON public.benefits USING btree (category);


--
-- Name: benefits_deleted_at_idx; Type: INDEX; Schema: public; Owner: -
--

CREATE INDEX benefits_deleted_at_idx ON public.benefits USING btree (deleted_at);


--
-- Name: benefits_evidence_idx; Type: INDEX; Schema: public; Owner: -
--

CREATE INDEX benefits_evidence_idx ON public.benefits USING btree (evidence_level);


--
-- Name: benefits_name_unique_idx; Type: INDEX; Schema: public; Owner: -
--

CREATE UNIQUE INDEX benefits_name_unique_idx ON public.benefits USING btree (lower((name)::text));


--
-- Name: calc_analytics_action_idx; Type: INDEX; Schema: public; Owner: -
--

CREATE INDEX calc_analytics_action_idx ON public.calc_analytics USING btree (action);


--
-- Name: calc_analytics_device_idx; Type: INDEX; Schema: public; Owner: -
--

CREATE INDEX calc_analytics_device_idx ON public.calc_analytics USING btree (device_uuid);


--
-- Name: calc_analytics_device_timestamp_action_idx; Type: INDEX; Schema: public; Owner: -
--

CREATE INDEX calc_analytics_device_timestamp_action_idx ON public.calc_analytics USING btree (device_uuid, "timestamp" DESC, action);


--
-- Name: calc_analytics_timestamp_idx; Type: INDEX; Schema: public; Owner: -
--

CREATE INDEX calc_analytics_timestamp_idx ON public.calc_analytics USING btree ("timestamp");


--
-- Name: calc_daily_stats_device_date_idx; Type: INDEX; Schema: public; Owner: -
--

CREATE UNIQUE INDEX calc_daily_stats_device_date_idx ON public.calc_daily_stats USING btree (device_uuid, date);


--
-- Name: calc_notification_devices_delivery_status_idx; Type: INDEX; Schema: public; Owner: -
--

CREATE INDEX calc_notification_devices_delivery_status_idx ON public.calc_notification_devices USING btree (delivery_status);


--
-- Name: calc_notification_devices_notification_device_unique; Type: INDEX; Schema: public; Owner: -
--

CREATE UNIQUE INDEX calc_notification_devices_notification_device_unique ON public.calc_notification_devices USING btree (notification_id, user_device_id);


--
-- Name: calc_notification_devices_notification_id_idx; Type: INDEX; Schema: public; Owner: -
--

CREATE INDEX calc_notification_devices_notification_id_idx ON public.calc_notification_devices USING btree (notification_id);


--
-- Name: calc_notification_devices_sent_at_idx; Type: INDEX; Schema: public; Owner: -
--

CREATE INDEX calc_notification_devices_sent_at_idx ON public.calc_notification_devices USING btree (sent_at);


--
-- Name: calc_notification_devices_user_device_id_idx; Type: INDEX; Schema: public; Owner: -
--

CREATE INDEX calc_notification_devices_user_device_id_idx ON public.calc_notification_devices USING btree (user_device_id);


--
-- Name: calc_notifications_created_at_idx; Type: INDEX; Schema: public; Owner: -
--

CREATE INDEX calc_notifications_created_at_idx ON public.calc_notifications USING btree (created_at);


--
-- Name: calc_notifications_resend_count_idx; Type: INDEX; Schema: public; Owner: -
--

CREATE INDEX calc_notifications_resend_count_idx ON public.calc_notifications USING btree (resend_count);


--
-- Name: calc_notifications_scheduled_at_idx; Type: INDEX; Schema: public; Owner: -
--

CREATE INDEX calc_notifications_scheduled_at_idx ON public.calc_notifications USING btree (scheduled_at);


--
-- Name: calc_notifications_scheduled_pending_idx; Type: INDEX; Schema: public; Owner: -
--

CREATE INDEX calc_notifications_scheduled_pending_idx ON public.calc_notifications USING btree (scheduled_at, user_id);


--
-- Name: calc_notifications_scheduled_status_idx; Type: INDEX; Schema: public; Owner: -
--

CREATE INDEX calc_notifications_scheduled_status_idx ON public.calc_notifications USING btree (scheduled_at, delivery_status);


--
-- Name: calc_notifications_user_id_idx; Type: INDEX; Schema: public; Owner: -
--

CREATE INDEX calc_notifications_user_id_idx ON public.calc_notifications USING btree (user_id);


--
-- Name: calc_promo_banners_banner_type_idx; Type: INDEX; Schema: public; Owner: -
--

CREATE INDEX calc_promo_banners_banner_type_idx ON public.calc_promo_banners USING btree (banner_type);


--
-- Name: calc_promo_banners_end_date_idx; Type: INDEX; Schema: public; Owner: -
--

CREATE INDEX calc_promo_banners_end_date_idx ON public.calc_promo_banners USING btree (end_date);


--
-- Name: calc_promo_banners_expires_at_idx; Type: INDEX; Schema: public; Owner: -
--

CREATE INDEX calc_promo_banners_expires_at_idx ON public.calc_promo_banners USING btree (expires_at);


--
-- Name: calc_promo_banners_is_active_idx; Type: INDEX; Schema: public; Owner: -
--

CREATE INDEX calc_promo_banners_is_active_idx ON public.calc_promo_banners USING btree (is_active);


--
-- Name: calc_promo_banners_is_visible_idx; Type: INDEX; Schema: public; Owner: -
--

CREATE INDEX calc_promo_banners_is_visible_idx ON public.calc_promo_banners USING btree (is_visible);


--
-- Name: calc_promo_banners_priority_idx; Type: INDEX; Schema: public; Owner: -
--

CREATE INDEX calc_promo_banners_priority_idx ON public.calc_promo_banners USING btree (priority);


--
-- Name: calc_promo_banners_start_date_idx; Type: INDEX; Schema: public; Owner: -
--

CREATE INDEX calc_promo_banners_start_date_idx ON public.calc_promo_banners USING btree (start_date);


--
-- Name: calc_user_devices_active_last_seen_idx; Type: INDEX; Schema: public; Owner: -
--

CREATE INDEX calc_user_devices_active_last_seen_idx ON public.calc_user_devices USING btree (is_active, last_seen);


--
-- Name: calc_user_devices_is_active_idx; Type: INDEX; Schema: public; Owner: -
--

CREATE INDEX calc_user_devices_is_active_idx ON public.calc_user_devices USING btree (is_active);


--
-- Name: calc_user_devices_last_seen_idx; Type: INDEX; Schema: public; Owner: -
--

CREATE INDEX calc_user_devices_last_seen_idx ON public.calc_user_devices USING btree (last_seen);


--
-- Name: calc_user_devices_platform_idx; Type: INDEX; Schema: public; Owner: -
--

CREATE INDEX calc_user_devices_platform_idx ON public.calc_user_devices USING btree (platform);


--
-- Name: calc_user_devices_user_device_unique; Type: INDEX; Schema: public; Owner: -
--

CREATE UNIQUE INDEX calc_user_devices_user_device_unique ON public.calc_user_devices USING btree (user_id, device_id);


--
-- Name: calc_user_devices_user_id_idx; Type: INDEX; Schema: public; Owner: -
--

CREATE INDEX calc_user_devices_user_id_idx ON public.calc_user_devices USING btree (user_id);


--
-- Name: calc_user_profiles_user_id_idx; Type: INDEX; Schema: public; Owner: -
--

CREATE UNIQUE INDEX calc_user_profiles_user_id_idx ON public.calc_user_profiles USING btree (user_id);


--
-- Name: calc_user_reviews_is_active_idx; Type: INDEX; Schema: public; Owner: -
--

CREATE INDEX calc_user_reviews_is_active_idx ON public.calc_user_reviews USING btree (is_active);


--
-- Name: calc_user_reviews_rating_idx; Type: INDEX; Schema: public; Owner: -
--

CREATE INDEX calc_user_reviews_rating_idx ON public.calc_user_reviews USING btree (rating);


--
-- Name: calc_user_reviews_user_id_idx; Type: INDEX; Schema: public; Owner: -
--

CREATE INDEX calc_user_reviews_user_id_idx ON public.calc_user_reviews USING btree (user_id);


--
-- Name: calc_vials_deleted_at_idx; Type: INDEX; Schema: public; Owner: -
--

CREATE INDEX calc_vials_deleted_at_idx ON public.calc_vials USING btree (deleted_at);


--
-- Name: calc_vials_is_active_idx; Type: INDEX; Schema: public; Owner: -
--

CREATE INDEX calc_vials_is_active_idx ON public.calc_vials USING btree (is_active);


--
-- Name: calc_vials_user_active_created_idx; Type: INDEX; Schema: public; Owner: -
--

CREATE INDEX calc_vials_user_active_created_idx ON public.calc_vials USING btree (user_id, is_active, created_at);


--
-- Name: calc_vials_user_id_idx; Type: INDEX; Schema: public; Owner: -
--

CREATE INDEX calc_vials_user_id_idx ON public.calc_vials USING btree (user_id);


--
-- Name: categories_deleted_at_idx; Type: INDEX; Schema: public; Owner: -
--

CREATE INDEX categories_deleted_at_idx ON public.categories USING btree (deleted_at);


--
-- Name: categories_name_unique_idx; Type: INDEX; Schema: public; Owner: -
--

CREATE UNIQUE INDEX categories_name_unique_idx ON public.categories USING btree (lower((category_name)::text));


--
-- Name: categories_parent_category_idx; Type: INDEX; Schema: public; Owner: -
--

CREATE INDEX categories_parent_category_idx ON public.categories USING btree (parent_category_id);


--
-- Name: citations_doi_idx; Type: INDEX; Schema: public; Owner: -
--

CREATE UNIQUE INDEX citations_doi_idx ON public.citations USING btree (doi);


--
-- Name: citations_journal_idx; Type: INDEX; Schema: public; Owner: -
--

CREATE INDEX citations_journal_idx ON public.citations USING btree (journal);


--
-- Name: citations_year_idx; Type: INDEX; Schema: public; Owner: -
--

CREATE INDEX citations_year_idx ON public.citations USING btree (publication_year);


--
-- Name: credit_accounts_balance_idx; Type: INDEX; Schema: public; Owner: -
--

CREATE INDEX credit_accounts_balance_idx ON public.credit_accounts USING btree (balance);


--
-- Name: credit_accounts_user_id_idx; Type: INDEX; Schema: public; Owner: -
--

CREATE UNIQUE INDEX credit_accounts_user_id_idx ON public.credit_accounts USING btree (user_id);


--
-- Name: credit_packages_active_idx; Type: INDEX; Schema: public; Owner: -
--

CREATE INDEX credit_packages_active_idx ON public.credit_packages USING btree (is_active);


--
-- Name: credit_packages_app_source_idx; Type: INDEX; Schema: public; Owner: -
--

CREATE INDEX credit_packages_app_source_idx ON public.credit_packages USING btree (app_source);


--
-- Name: credit_packages_sort_order_idx; Type: INDEX; Schema: public; Owner: -
--

CREATE INDEX credit_packages_sort_order_idx ON public.credit_packages USING btree (sort_order);


--
-- Name: credit_packages_stripe_price_id_idx; Type: INDEX; Schema: public; Owner: -
--

CREATE UNIQUE INDEX credit_packages_stripe_price_id_idx ON public.credit_packages USING btree (stripe_price_id);


--
-- Name: credit_transactions_app_source_idx; Type: INDEX; Schema: public; Owner: -
--

CREATE INDEX credit_transactions_app_source_idx ON public.credit_transactions USING btree (app_source);


--
-- Name: credit_transactions_created_at_idx; Type: INDEX; Schema: public; Owner: -
--

CREATE INDEX credit_transactions_created_at_idx ON public.credit_transactions USING btree (created_at);


--
-- Name: credit_transactions_credit_account_id_idx; Type: INDEX; Schema: public; Owner: -
--

CREATE INDEX credit_transactions_credit_account_id_idx ON public.credit_transactions USING btree (credit_account_id);


--
-- Name: credit_transactions_credit_package_id_idx; Type: INDEX; Schema: public; Owner: -
--

CREATE INDEX credit_transactions_credit_package_id_idx ON public.credit_transactions USING btree (credit_package_id);


--
-- Name: credit_transactions_purchase_ref_uniq_idx; Type: INDEX; Schema: public; Owner: -
--

CREATE UNIQUE INDEX credit_transactions_purchase_ref_uniq_idx ON public.credit_transactions USING btree (reference_id) WHERE ((type = 'purchase'::public.credit_transaction_type) AND (reference_id IS NOT NULL));


--
-- Name: credit_transactions_reference_id_idx; Type: INDEX; Schema: public; Owner: -
--

CREATE INDEX credit_transactions_reference_id_idx ON public.credit_transactions USING btree (reference_id);


--
-- Name: credit_transactions_type_idx; Type: INDEX; Schema: public; Owner: -
--

CREATE INDEX credit_transactions_type_idx ON public.credit_transactions USING btree (type);


--
-- Name: credit_transactions_user_created_idx; Type: INDEX; Schema: public; Owner: -
--

CREATE INDEX credit_transactions_user_created_idx ON public.credit_transactions USING btree (user_id, created_at);


--
-- Name: credit_transactions_user_id_idx; Type: INDEX; Schema: public; Owner: -
--

CREATE INDEX credit_transactions_user_id_idx ON public.credit_transactions USING btree (user_id);


--
-- Name: dosages_active_order_idx; Type: INDEX; Schema: public; Owner: -
--

CREATE INDEX dosages_active_order_idx ON public.dosages USING btree (is_active, sort_order);


--
-- Name: dosages_amount_unit_name_severity_unique; Type: INDEX; Schema: public; Owner: -
--

CREATE UNIQUE INDEX dosages_amount_unit_name_severity_unique ON public.dosages USING btree (amount, unit, name, severity_level);


--
-- Name: dosages_deleted_at_idx; Type: INDEX; Schema: public; Owner: -
--

CREATE INDEX dosages_deleted_at_idx ON public.dosages USING btree (deleted_at);


--
-- Name: dosages_severity_active_idx; Type: INDEX; Schema: public; Owner: -
--

CREATE INDEX dosages_severity_active_idx ON public.dosages USING btree (severity_level, is_active);


--
-- Name: feedback_questions_active_order_idx; Type: INDEX; Schema: public; Owner: -
--

CREATE INDEX feedback_questions_active_order_idx ON public.feedback_questions USING btree (is_active, sort_order);


--
-- Name: feedback_questions_code_idx; Type: INDEX; Schema: public; Owner: -
--

CREATE UNIQUE INDEX feedback_questions_code_idx ON public.feedback_questions USING btree (question_code);


--
-- Name: feedback_questions_deleted_at_idx; Type: INDEX; Schema: public; Owner: -
--

CREATE INDEX feedback_questions_deleted_at_idx ON public.feedback_questions USING btree (deleted_at);


--
-- Name: influencer_profiles_is_active_idx; Type: INDEX; Schema: public; Owner: -
--

CREATE INDEX influencer_profiles_is_active_idx ON public.influencer_profiles USING btree (is_active);


--
-- Name: influencer_profiles_referral_code_idx; Type: INDEX; Schema: public; Owner: -
--

CREATE INDEX influencer_profiles_referral_code_idx ON public.influencer_profiles USING btree (referral_code);


--
-- Name: influencer_profiles_user_id_idx; Type: INDEX; Schema: public; Owner: -
--

CREATE UNIQUE INDEX influencer_profiles_user_id_idx ON public.influencer_profiles USING btree (user_id);


--
-- Name: pepti_price_analytics_action_idx; Type: INDEX; Schema: public; Owner: -
--

CREATE INDEX pepti_price_analytics_action_idx ON public.pepti_price_analytics USING btree (action);


--
-- Name: pepti_price_analytics_peptide_idx; Type: INDEX; Schema: public; Owner: -
--

CREATE INDEX pepti_price_analytics_peptide_idx ON public.pepti_price_analytics USING btree (peptide_id);


--
-- Name: pepti_price_analytics_peptide_timestamp_idx; Type: INDEX; Schema: public; Owner: -
--

CREATE INDEX pepti_price_analytics_peptide_timestamp_idx ON public.pepti_price_analytics USING btree (peptide_id, "timestamp" DESC);


--
-- Name: pepti_price_analytics_timestamp_idx; Type: INDEX; Schema: public; Owner: -
--

CREATE INDEX pepti_price_analytics_timestamp_idx ON public.pepti_price_analytics USING btree ("timestamp");


--
-- Name: pepti_price_analytics_vendor_idx; Type: INDEX; Schema: public; Owner: -
--

CREATE INDEX pepti_price_analytics_vendor_idx ON public.pepti_price_analytics USING btree (vendor_id);


--
-- Name: pepti_price_daily_stats_peptide_date_idx; Type: INDEX; Schema: public; Owner: -
--

CREATE UNIQUE INDEX pepti_price_daily_stats_peptide_date_idx ON public.pepti_price_daily_stats USING btree (peptide_id, date);


--
-- Name: pepti_price_history_peptide_admin_dosage_idx; Type: INDEX; Schema: public; Owner: -
--

CREATE INDEX pepti_price_history_peptide_admin_dosage_idx ON public.pepti_price_price_history USING btree (peptide_id, administration_method_id, dosage_id);


--
-- Name: pepti_price_history_recorded_at_idx; Type: INDEX; Schema: public; Owner: -
--

CREATE INDEX pepti_price_history_recorded_at_idx ON public.pepti_price_price_history USING btree (recorded_at);


--
-- Name: pepti_price_history_vendor_idx; Type: INDEX; Schema: public; Owner: -
--

CREATE INDEX pepti_price_history_vendor_idx ON public.pepti_price_price_history USING btree (vendor_id);


--
-- Name: pepti_price_newsletter_email_idx; Type: INDEX; Schema: public; Owner: -
--

CREATE UNIQUE INDEX pepti_price_newsletter_email_idx ON public.pepti_price_newsletter_subscribers USING btree (email);


--
-- Name: pepti_price_newsletter_unsubscribed_idx; Type: INDEX; Schema: public; Owner: -
--

CREATE INDEX pepti_price_newsletter_unsubscribed_idx ON public.pepti_price_newsletter_subscribers USING btree (unsubscribed_at);


--
-- Name: pepti_price_notifications_created_idx; Type: INDEX; Schema: public; Owner: -
--

CREATE INDEX pepti_price_notifications_created_idx ON public.pepti_price_notifications USING btree (created_at);


--
-- Name: pepti_price_notifications_user_idx; Type: INDEX; Schema: public; Owner: -
--

CREATE INDEX pepti_price_notifications_user_idx ON public.pepti_price_notifications USING btree (user_id);


--
-- Name: pepti_price_notifications_user_read_idx; Type: INDEX; Schema: public; Owner: -
--

CREATE INDEX pepti_price_notifications_user_read_idx ON public.pepti_price_notifications USING btree (user_id, read_at);


--
-- Name: pepti_price_promo_codes_active_idx; Type: INDEX; Schema: public; Owner: -
--

CREATE INDEX pepti_price_promo_codes_active_idx ON public.pepti_price_promo_codes USING btree (is_active);


--
-- Name: pepti_price_promo_codes_code_unique_idx; Type: INDEX; Schema: public; Owner: -
--

CREATE UNIQUE INDEX pepti_price_promo_codes_code_unique_idx ON public.pepti_price_promo_codes USING btree (lower((code)::text));


--
-- Name: pepti_price_vendor_pricing_admin_method_idx; Type: INDEX; Schema: public; Owner: -
--

CREATE INDEX pepti_price_vendor_pricing_admin_method_idx ON public.pepti_price_vendor_pricing USING btree (administration_method_id);


--
-- Name: pepti_price_vendor_pricing_dosage_idx; Type: INDEX; Schema: public; Owner: -
--

CREATE INDEX pepti_price_vendor_pricing_dosage_idx ON public.pepti_price_vendor_pricing USING btree (dosage_id);


--
-- Name: pepti_price_vendor_pricing_peptide_idx; Type: INDEX; Schema: public; Owner: -
--

CREATE INDEX pepti_price_vendor_pricing_peptide_idx ON public.pepti_price_vendor_pricing USING btree (peptide_id);


--
-- Name: pepti_price_vendor_pricing_promo_code_idx; Type: INDEX; Schema: public; Owner: -
--

CREATE INDEX pepti_price_vendor_pricing_promo_code_idx ON public.pepti_price_vendor_pricing USING btree (promo_code_id);


--
-- Name: pepti_price_vendor_pricing_status_idx; Type: INDEX; Schema: public; Owner: -
--

CREATE INDEX pepti_price_vendor_pricing_status_idx ON public.pepti_price_vendor_pricing USING btree (status);


--
-- Name: pepti_price_vendor_pricing_unique_idx; Type: INDEX; Schema: public; Owner: -
--

CREATE UNIQUE INDEX pepti_price_vendor_pricing_unique_idx ON public.pepti_price_vendor_pricing USING btree (peptide_id, vendor_id, administration_method_id, dosage_value);


--
-- Name: pepti_price_vendor_pricing_vendor_idx; Type: INDEX; Schema: public; Owner: -
--

CREATE INDEX pepti_price_vendor_pricing_vendor_idx ON public.pepti_price_vendor_pricing USING btree (vendor_id);


--
-- Name: pepti_price_watchlist_peptide_idx; Type: INDEX; Schema: public; Owner: -
--

CREATE INDEX pepti_price_watchlist_peptide_idx ON public.pepti_price_watchlist USING btree (peptide_id);


--
-- Name: pepti_price_watchlist_user_peptide_idx; Type: INDEX; Schema: public; Owner: -
--

CREATE UNIQUE INDEX pepti_price_watchlist_user_peptide_idx ON public.pepti_price_watchlist USING btree (user_id, peptide_id);


--
-- Name: peptide_benefits_benefit_idx; Type: INDEX; Schema: public; Owner: -
--

CREATE INDEX peptide_benefits_benefit_idx ON public.peptide_benefits USING btree (benefit_id);


--
-- Name: peptide_benefits_peptide_idx; Type: INDEX; Schema: public; Owner: -
--

CREATE INDEX peptide_benefits_peptide_idx ON public.peptide_benefits USING btree (peptide_id);


--
-- Name: peptide_benefits_unique; Type: INDEX; Schema: public; Owner: -
--

CREATE UNIQUE INDEX peptide_benefits_unique ON public.peptide_benefits USING btree (peptide_id, benefit_id);


--
-- Name: peptide_interactions_peptide1_idx; Type: INDEX; Schema: public; Owner: -
--

CREATE INDEX peptide_interactions_peptide1_idx ON public.peptide_interactions USING btree (peptide_id_1);


--
-- Name: peptide_interactions_peptide2_idx; Type: INDEX; Schema: public; Owner: -
--

CREATE INDEX peptide_interactions_peptide2_idx ON public.peptide_interactions USING btree (peptide_id_2);


--
-- Name: peptide_interactions_type_idx; Type: INDEX; Schema: public; Owner: -
--

CREATE INDEX peptide_interactions_type_idx ON public.peptide_interactions USING btree (interaction_type);


--
-- Name: peptide_interactions_unique_pair; Type: INDEX; Schema: public; Owner: -
--

CREATE UNIQUE INDEX peptide_interactions_unique_pair ON public.peptide_interactions USING btree (LEAST(peptide_id_1, COALESCE(peptide_id_2, '-1'::integer)), GREATEST(peptide_id_1, COALESCE(peptide_id_2, '-1'::integer)));


--
-- Name: peptide_protocols_admin_active_idx; Type: INDEX; Schema: public; Owner: -
--

CREATE INDEX peptide_protocols_admin_active_idx ON public.peptide_protocols USING btree (administration_method_id, is_active);


--
-- Name: peptide_protocols_deleted_at_idx; Type: INDEX; Schema: public; Owner: -
--

CREATE INDEX peptide_protocols_deleted_at_idx ON public.peptide_protocols USING btree (deleted_at);


--
-- Name: peptide_protocols_peptide_active_idx; Type: INDEX; Schema: public; Owner: -
--

CREATE INDEX peptide_protocols_peptide_active_idx ON public.peptide_protocols USING btree (peptide_id, is_active);


--
-- Name: peptide_protocols_peptide_admin_unique; Type: INDEX; Schema: public; Owner: -
--

CREATE UNIQUE INDEX peptide_protocols_peptide_admin_unique ON public.peptide_protocols USING btree (peptide_id, administration_method_id);


--
-- Name: peptide_question_assignment_unique; Type: INDEX; Schema: public; Owner: -
--

CREATE UNIQUE INDEX peptide_question_assignment_unique ON public.peptide_question_assignments USING btree (peptide_id, question_id);


--
-- Name: peptide_question_assignments_peptide_idx; Type: INDEX; Schema: public; Owner: -
--

CREATE INDEX peptide_question_assignments_peptide_idx ON public.peptide_question_assignments USING btree (peptide_id);


--
-- Name: peptide_question_assignments_peptide_order_idx; Type: INDEX; Schema: public; Owner: -
--

CREATE INDEX peptide_question_assignments_peptide_order_idx ON public.peptide_question_assignments USING btree (peptide_id, sort_order);


--
-- Name: peptide_question_assignments_question_idx; Type: INDEX; Schema: public; Owner: -
--

CREATE INDEX peptide_question_assignments_question_idx ON public.peptide_question_assignments USING btree (question_id);


--
-- Name: peptide_question_options_deleted_at_idx; Type: INDEX; Schema: public; Owner: -
--

CREATE INDEX peptide_question_options_deleted_at_idx ON public.peptide_question_options USING btree (deleted_at);


--
-- Name: peptide_questions_deleted_at_idx; Type: INDEX; Schema: public; Owner: -
--

CREATE INDEX peptide_questions_deleted_at_idx ON public.peptide_questions USING btree (deleted_at);


--
-- Name: peptide_references_citation_idx; Type: INDEX; Schema: public; Owner: -
--

CREATE INDEX peptide_references_citation_idx ON public.peptide_references USING btree (citation_id);


--
-- Name: peptide_references_peptide_idx; Type: INDEX; Schema: public; Owner: -
--

CREATE INDEX peptide_references_peptide_idx ON public.peptide_references USING btree (peptide_id, reference_type);


--
-- Name: peptide_references_study_idx; Type: INDEX; Schema: public; Owner: -
--

CREATE INDEX peptide_references_study_idx ON public.peptide_references USING btree (study_id);


--
-- Name: peptide_research_indication_studies_indication_idx; Type: INDEX; Schema: public; Owner: -
--

CREATE INDEX peptide_research_indication_studies_indication_idx ON public.peptide_research_indication_studies USING btree (indication_id);


--
-- Name: peptide_research_indication_studies_indication_protocol_idx; Type: INDEX; Schema: public; Owner: -
--

CREATE INDEX peptide_research_indication_studies_indication_protocol_idx ON public.peptide_research_indication_studies USING btree (indication_id, protocol_id);


--
-- Name: peptide_research_indication_studies_protocol_idx; Type: INDEX; Schema: public; Owner: -
--

CREATE INDEX peptide_research_indication_studies_protocol_idx ON public.peptide_research_indication_studies USING btree (protocol_id);


--
-- Name: peptide_research_indications_effectiveness_idx; Type: INDEX; Schema: public; Owner: -
--

CREATE INDEX peptide_research_indications_effectiveness_idx ON public.peptide_research_indications USING btree (effectiveness_tag);


--
-- Name: peptide_research_indications_peptide_idx; Type: INDEX; Schema: public; Owner: -
--

CREATE INDEX peptide_research_indications_peptide_idx ON public.peptide_research_indications USING btree (peptide_id);


--
-- Name: peptide_research_indications_peptide_indication_idx; Type: INDEX; Schema: public; Owner: -
--

CREATE INDEX peptide_research_indications_peptide_indication_idx ON public.peptide_research_indications USING btree (peptide_id, indication_title);


--
-- Name: peptide_side_effects_peptide_idx; Type: INDEX; Schema: public; Owner: -
--

CREATE INDEX peptide_side_effects_peptide_idx ON public.peptide_side_effects USING btree (peptide_id);


--
-- Name: peptide_side_effects_side_effect_idx; Type: INDEX; Schema: public; Owner: -
--

CREATE INDEX peptide_side_effects_side_effect_idx ON public.peptide_side_effects USING btree (side_effect_id);


--
-- Name: peptide_side_effects_unique; Type: INDEX; Schema: public; Owner: -
--

CREATE UNIQUE INDEX peptide_side_effects_unique ON public.peptide_side_effects USING btree (peptide_id, side_effect_id);


--
-- Name: peptides_category_created_idx; Type: INDEX; Schema: public; Owner: -
--

CREATE INDEX peptides_category_created_idx ON public.peptides USING btree (category_id, created_at DESC);


--
-- Name: peptides_category_fda_idx; Type: INDEX; Schema: public; Owner: -
--

CREATE INDEX peptides_category_fda_idx ON public.peptides USING btree (category_id, fda_approval_status);


--
-- Name: peptides_category_id_idx; Type: INDEX; Schema: public; Owner: -
--

CREATE INDEX peptides_category_id_idx ON public.peptides USING btree (category_id);


--
-- Name: peptides_category_research_idx; Type: INDEX; Schema: public; Owner: -
--

CREATE INDEX peptides_category_research_idx ON public.peptides USING btree (category_id, research_level);


--
-- Name: peptides_created_at_idx; Type: INDEX; Schema: public; Owner: -
--

CREATE INDEX peptides_created_at_idx ON public.peptides USING btree (created_at);


--
-- Name: peptides_deleted_at_idx; Type: INDEX; Schema: public; Owner: -
--

CREATE INDEX peptides_deleted_at_idx ON public.peptides USING btree (deleted_at);


--
-- Name: peptides_fda_status_idx; Type: INDEX; Schema: public; Owner: -
--

CREATE INDEX peptides_fda_status_idx ON public.peptides USING btree (fda_approval_status);


--
-- Name: peptides_name_idx; Type: INDEX; Schema: public; Owner: -
--

CREATE INDEX peptides_name_idx ON public.peptides USING btree (name);


--
-- Name: peptides_name_unique_idx; Type: INDEX; Schema: public; Owner: -
--

CREATE UNIQUE INDEX peptides_name_unique_idx ON public.peptides USING btree (lower((name)::text));


--
-- Name: peptides_popular_idx; Type: INDEX; Schema: public; Owner: -
--

CREATE INDEX peptides_popular_idx ON public.peptides USING btree (is_popular);


--
-- Name: peptides_research_level_idx; Type: INDEX; Schema: public; Owner: -
--

CREATE INDEX peptides_research_level_idx ON public.peptides USING btree (research_level);


--
-- Name: peptides_wada_status_idx; Type: INDEX; Schema: public; Owner: -
--

CREATE INDEX peptides_wada_status_idx ON public.peptides USING btree (wada_status);


--
-- Name: protocol_application_places_place_idx; Type: INDEX; Schema: public; Owner: -
--

CREATE INDEX protocol_application_places_place_idx ON public.protocol_application_places USING btree (application_place_id);


--
-- Name: protocol_application_places_protocol_idx; Type: INDEX; Schema: public; Owner: -
--

CREATE INDEX protocol_application_places_protocol_idx ON public.protocol_application_places USING btree (protocol_id);


--
-- Name: protocol_application_places_unique; Type: INDEX; Schema: public; Owner: -
--

CREATE UNIQUE INDEX protocol_application_places_unique ON public.protocol_application_places USING btree (protocol_id, application_place_id);


--
-- Name: protocol_dosage_benefits_benefit_idx; Type: INDEX; Schema: public; Owner: -
--

CREATE INDEX protocol_dosage_benefits_benefit_idx ON public.protocol_dosage_benefits USING btree (benefit_id);


--
-- Name: protocol_dosage_benefits_evidence_idx; Type: INDEX; Schema: public; Owner: -
--

CREATE INDEX protocol_dosage_benefits_evidence_idx ON public.protocol_dosage_benefits USING btree (evidence_quality);


--
-- Name: protocol_dosage_benefits_potency_idx; Type: INDEX; Schema: public; Owner: -
--

CREATE INDEX protocol_dosage_benefits_potency_idx ON public.protocol_dosage_benefits USING btree (potency);


--
-- Name: protocol_dosage_benefits_protocol_idx; Type: INDEX; Schema: public; Owner: -
--

CREATE INDEX protocol_dosage_benefits_protocol_idx ON public.protocol_dosage_benefits USING btree (protocol_dosage_id);


--
-- Name: protocol_dosage_benefits_unique; Type: INDEX; Schema: public; Owner: -
--

CREATE UNIQUE INDEX protocol_dosage_benefits_unique ON public.protocol_dosage_benefits USING btree (protocol_dosage_id, benefit_id);


--
-- Name: protocol_dosages_default_protocol_idx; Type: INDEX; Schema: public; Owner: -
--

CREATE INDEX protocol_dosages_default_protocol_idx ON public.protocol_dosages USING btree (is_default, protocol_id);


--
-- Name: protocol_dosages_dosage_idx; Type: INDEX; Schema: public; Owner: -
--

CREATE INDEX protocol_dosages_dosage_idx ON public.protocol_dosages USING btree (dosage_id);


--
-- Name: protocol_dosages_protocol_default_order_idx; Type: INDEX; Schema: public; Owner: -
--

CREATE INDEX protocol_dosages_protocol_default_order_idx ON public.protocol_dosages USING btree (protocol_id, is_default, sort_order);


--
-- Name: protocol_dosages_protocol_dosage_schedule_idx; Type: INDEX; Schema: public; Owner: -
--

CREATE INDEX protocol_dosages_protocol_dosage_schedule_idx ON public.protocol_dosages USING btree (protocol_id, dosage_id, schedule_id);


--
-- Name: protocol_dosages_protocol_idx; Type: INDEX; Schema: public; Owner: -
--

CREATE INDEX protocol_dosages_protocol_idx ON public.protocol_dosages USING btree (protocol_id);


--
-- Name: protocol_dosages_protocol_order_idx; Type: INDEX; Schema: public; Owner: -
--

CREATE INDEX protocol_dosages_protocol_order_idx ON public.protocol_dosages USING btree (protocol_id, sort_order);


--
-- Name: protocol_dosages_required_protocol_idx; Type: INDEX; Schema: public; Owner: -
--

CREATE INDEX protocol_dosages_required_protocol_idx ON public.protocol_dosages USING btree (is_required, protocol_id);


--
-- Name: protocol_dosages_schedule_idx; Type: INDEX; Schema: public; Owner: -
--

CREATE INDEX protocol_dosages_schedule_idx ON public.protocol_dosages USING btree (schedule_id);


--
-- Name: protocol_quality_indicators_protocol_idx; Type: INDEX; Schema: public; Owner: -
--

CREATE INDEX protocol_quality_indicators_protocol_idx ON public.protocol_quality_indicators USING btree (protocol_id);


--
-- Name: protocol_quality_indicators_protocol_order_idx; Type: INDEX; Schema: public; Owner: -
--

CREATE INDEX protocol_quality_indicators_protocol_order_idx ON public.protocol_quality_indicators USING btree (protocol_id, sort_order);


--
-- Name: protocol_side_effects_protocol_dosage_idx; Type: INDEX; Schema: public; Owner: -
--

CREATE INDEX protocol_side_effects_protocol_dosage_idx ON public.protocol_dosage_side_effects USING btree (protocol_dosage_id);


--
-- Name: protocol_side_effects_side_effect_idx; Type: INDEX; Schema: public; Owner: -
--

CREATE INDEX protocol_side_effects_side_effect_idx ON public.protocol_dosage_side_effects USING btree (side_effect_id);


--
-- Name: protocol_side_effects_unique; Type: INDEX; Schema: public; Owner: -
--

CREATE UNIQUE INDEX protocol_side_effects_unique ON public.protocol_dosage_side_effects USING btree (protocol_dosage_id, side_effect_id);


--
-- Name: protocol_step_unique; Type: INDEX; Schema: public; Owner: -
--

CREATE UNIQUE INDEX protocol_step_unique ON public.peptide_protocol_reconstitution_steps USING btree (protocol_id, step_number);


--
-- Name: question_option_assignment_unique; Type: INDEX; Schema: public; Owner: -
--

CREATE UNIQUE INDEX question_option_assignment_unique ON public.peptide_question_option_assignments USING btree (question_id, question_option_id);


--
-- Name: question_option_assignments_active_idx; Type: INDEX; Schema: public; Owner: -
--

CREATE INDEX question_option_assignments_active_idx ON public.peptide_question_option_assignments USING btree (is_active);


--
-- Name: question_option_assignments_option_idx; Type: INDEX; Schema: public; Owner: -
--

CREATE INDEX question_option_assignments_option_idx ON public.peptide_question_option_assignments USING btree (question_option_id);


--
-- Name: question_option_assignments_question_idx; Type: INDEX; Schema: public; Owner: -
--

CREATE INDEX question_option_assignments_question_idx ON public.peptide_question_option_assignments USING btree (question_id);


--
-- Name: question_option_assignments_question_order_idx; Type: INDEX; Schema: public; Owner: -
--

CREATE INDEX question_option_assignments_question_order_idx ON public.peptide_question_option_assignments USING btree (question_id, sort_order);


--
-- Name: research_studies_title_idx; Type: INDEX; Schema: public; Owner: -
--

CREATE INDEX research_studies_title_idx ON public.research_studies USING btree (title);


--
-- Name: research_studies_year_idx; Type: INDEX; Schema: public; Owner: -
--

CREATE INDEX research_studies_year_idx ON public.research_studies USING btree (publication_year);


--
-- Name: roles_name_idx; Type: INDEX; Schema: public; Owner: -
--

CREATE UNIQUE INDEX roles_name_idx ON public.roles USING btree (name);


--
-- Name: schedules_active_order_idx; Type: INDEX; Schema: public; Owner: -
--

CREATE INDEX schedules_active_order_idx ON public.schedules USING btree (is_active, sort_order);


--
-- Name: schedules_deleted_at_idx; Type: INDEX; Schema: public; Owner: -
--

CREATE INDEX schedules_deleted_at_idx ON public.schedules USING btree (deleted_at);


--
-- Name: schedules_name_frequency_unique; Type: INDEX; Schema: public; Owner: -
--

CREATE UNIQUE INDEX schedules_name_frequency_unique ON public.schedules USING btree (lower((name)::text), lower((frequency)::text));


--
-- Name: sds_analytics_action_idx; Type: INDEX; Schema: public; Owner: -
--

CREATE INDEX sds_analytics_action_idx ON public.sds_analytics USING btree (action);


--
-- Name: sds_analytics_action_timestamp_idx; Type: INDEX; Schema: public; Owner: -
--

CREATE INDEX sds_analytics_action_timestamp_idx ON public.sds_analytics USING btree (action, "timestamp" DESC);


--
-- Name: sds_analytics_compound_idx; Type: INDEX; Schema: public; Owner: -
--

CREATE INDEX sds_analytics_compound_idx ON public.sds_analytics USING btree (compound_id);


--
-- Name: sds_analytics_timestamp_idx; Type: INDEX; Schema: public; Owner: -
--

CREATE INDEX sds_analytics_timestamp_idx ON public.sds_analytics USING btree ("timestamp");


--
-- Name: sds_batches_created_at_idx; Type: INDEX; Schema: public; Owner: -
--

CREATE INDEX sds_batches_created_at_idx ON public.sds_batches USING btree (created_at);


--
-- Name: sds_batches_status_idx; Type: INDEX; Schema: public; Owner: -
--

CREATE INDEX sds_batches_status_idx ON public.sds_batches USING btree (status);


--
-- Name: sds_compounds_cas_number_idx; Type: INDEX; Schema: public; Owner: -
--

CREATE INDEX sds_compounds_cas_number_idx ON public.sds_compounds USING btree (cas_number);


--
-- Name: sds_compounds_deleted_at_idx; Type: INDEX; Schema: public; Owner: -
--

CREATE INDEX sds_compounds_deleted_at_idx ON public.sds_compounds USING btree (deleted_at);


--
-- Name: sds_compounds_fetch_status_idx; Type: INDEX; Schema: public; Owner: -
--

CREATE INDEX sds_compounds_fetch_status_idx ON public.sds_compounds USING btree (fetch_status);


--
-- Name: sds_compounds_name_idx; Type: INDEX; Schema: public; Owner: -
--

CREATE INDEX sds_compounds_name_idx ON public.sds_compounds USING btree (name);


--
-- Name: sds_compounds_peptide_id_idx; Type: INDEX; Schema: public; Owner: -
--

CREATE INDEX sds_compounds_peptide_id_idx ON public.sds_compounds USING btree (peptide_id);


--
-- Name: sds_compounds_pubchem_cid_idx; Type: INDEX; Schema: public; Owner: -
--

CREATE UNIQUE INDEX sds_compounds_pubchem_cid_idx ON public.sds_compounds USING btree (pubchem_cid);


--
-- Name: sds_documents_company_name_idx; Type: INDEX; Schema: public; Owner: -
--

CREATE INDEX sds_documents_company_name_idx ON public.sds_documents USING btree (company_name);


--
-- Name: sds_documents_compound_id_idx; Type: INDEX; Schema: public; Owner: -
--

CREATE INDEX sds_documents_compound_id_idx ON public.sds_documents USING btree (compound_id);


--
-- Name: sds_documents_deleted_at_idx; Type: INDEX; Schema: public; Owner: -
--

CREATE INDEX sds_documents_deleted_at_idx ON public.sds_documents USING btree (deleted_at);


--
-- Name: sds_documents_generated_at_idx; Type: INDEX; Schema: public; Owner: -
--

CREATE INDEX sds_documents_generated_at_idx ON public.sds_documents USING btree (generated_at);


--
-- Name: sds_documents_user_id_idx; Type: INDEX; Schema: public; Owner: -
--

CREATE INDEX sds_documents_user_id_idx ON public.sds_documents USING btree (user_id);


--
-- Name: sds_hazard_data_compound_id_idx; Type: INDEX; Schema: public; Owner: -
--

CREATE INDEX sds_hazard_data_compound_id_idx ON public.sds_hazard_data USING btree (compound_id);


--
-- Name: sds_hazard_data_deleted_at_idx; Type: INDEX; Schema: public; Owner: -
--

CREATE INDEX sds_hazard_data_deleted_at_idx ON public.sds_hazard_data USING btree (deleted_at);


--
-- Name: sds_hazard_data_signal_word_idx; Type: INDEX; Schema: public; Owner: -
--

CREATE INDEX sds_hazard_data_signal_word_idx ON public.sds_hazard_data USING btree (signal_word);


--
-- Name: sds_job_queue_compound_id_idx; Type: INDEX; Schema: public; Owner: -
--

CREATE INDEX sds_job_queue_compound_id_idx ON public.sds_job_queue USING btree (compound_id);


--
-- Name: sds_job_queue_created_at_idx; Type: INDEX; Schema: public; Owner: -
--

CREATE INDEX sds_job_queue_created_at_idx ON public.sds_job_queue USING btree (created_at);


--
-- Name: sds_job_queue_status_priority_idx; Type: INDEX; Schema: public; Owner: -
--

CREATE INDEX sds_job_queue_status_priority_idx ON public.sds_job_queue USING btree (status, priority);


--
-- Name: sds_job_queue_type_idx; Type: INDEX; Schema: public; Owner: -
--

CREATE INDEX sds_job_queue_type_idx ON public.sds_job_queue USING btree (type);


--
-- Name: sds_job_queue_user_id_idx; Type: INDEX; Schema: public; Owner: -
--

CREATE INDEX sds_job_queue_user_id_idx ON public.sds_job_queue USING btree (user_id);


--
-- Name: sds_pdf_templates_default_idx; Type: INDEX; Schema: public; Owner: -
--

CREATE UNIQUE INDEX sds_pdf_templates_default_idx ON public.sds_pdf_templates USING btree (is_default) WHERE (is_default = true);


--
-- Name: sds_pdf_templates_deleted_at_idx; Type: INDEX; Schema: public; Owner: -
--

CREATE INDEX sds_pdf_templates_deleted_at_idx ON public.sds_pdf_templates USING btree (deleted_at);


--
-- Name: sds_pdf_templates_name_idx; Type: INDEX; Schema: public; Owner: -
--

CREATE INDEX sds_pdf_templates_name_idx ON public.sds_pdf_templates USING btree (name);


--
-- Name: sds_pinned_compounds_category_idx; Type: INDEX; Schema: public; Owner: -
--

CREATE INDEX sds_pinned_compounds_category_idx ON public.sds_pinned_compounds USING btree (category);


--
-- Name: sds_pinned_compounds_compound_id_idx; Type: INDEX; Schema: public; Owner: -
--

CREATE INDEX sds_pinned_compounds_compound_id_idx ON public.sds_pinned_compounds USING btree (compound_id);


--
-- Name: sds_pinned_compounds_deleted_at_idx; Type: INDEX; Schema: public; Owner: -
--

CREATE INDEX sds_pinned_compounds_deleted_at_idx ON public.sds_pinned_compounds USING btree (deleted_at);


--
-- Name: sds_pinned_compounds_pubchem_cid_unique; Type: INDEX; Schema: public; Owner: -
--

CREATE UNIQUE INDEX sds_pinned_compounds_pubchem_cid_unique ON public.sds_pinned_compounds USING btree (pubchem_cid);


--
-- Name: sds_pinned_compounds_sort_order_idx; Type: INDEX; Schema: public; Owner: -
--

CREATE INDEX sds_pinned_compounds_sort_order_idx ON public.sds_pinned_compounds USING btree (sort_order);


--
-- Name: sds_pinned_compounds_verified_idx; Type: INDEX; Schema: public; Owner: -
--

CREATE INDEX sds_pinned_compounds_verified_idx ON public.sds_pinned_compounds USING btree (verified);


--
-- Name: sds_sections_compound_id_idx; Type: INDEX; Schema: public; Owner: -
--

CREATE INDEX sds_sections_compound_id_idx ON public.sds_sections USING btree (compound_id);


--
-- Name: sds_sections_deleted_at_idx; Type: INDEX; Schema: public; Owner: -
--

CREATE INDEX sds_sections_deleted_at_idx ON public.sds_sections USING btree (deleted_at);


--
-- Name: side_effects_active_order_idx; Type: INDEX; Schema: public; Owner: -
--

CREATE INDEX side_effects_active_order_idx ON public.side_effects USING btree (is_active, sort_order);


--
-- Name: side_effects_category_idx; Type: INDEX; Schema: public; Owner: -
--

CREATE INDEX side_effects_category_idx ON public.side_effects USING btree (category);


--
-- Name: side_effects_deleted_at_idx; Type: INDEX; Schema: public; Owner: -
--

CREATE INDEX side_effects_deleted_at_idx ON public.side_effects USING btree (deleted_at);


--
-- Name: side_effects_frequency_idx; Type: INDEX; Schema: public; Owner: -
--

CREATE INDEX side_effects_frequency_idx ON public.side_effects USING btree (frequency);


--
-- Name: side_effects_name_unique_idx; Type: INDEX; Schema: public; Owner: -
--

CREATE UNIQUE INDEX side_effects_name_unique_idx ON public.side_effects USING btree (lower((name)::text));


--
-- Name: side_effects_severity_category_idx; Type: INDEX; Schema: public; Owner: -
--

CREATE INDEX side_effects_severity_category_idx ON public.side_effects USING btree (severity_level, category);


--
-- Name: side_effects_severity_idx; Type: INDEX; Schema: public; Owner: -
--

CREATE INDEX side_effects_severity_idx ON public.side_effects USING btree (severity_level);


--
-- Name: stripe_customers_stripe_customer_id_idx; Type: INDEX; Schema: public; Owner: -
--

CREATE UNIQUE INDEX stripe_customers_stripe_customer_id_idx ON public.stripe_customers USING btree (stripe_customer_id);


--
-- Name: stripe_customers_user_id_idx; Type: INDEX; Schema: public; Owner: -
--

CREATE UNIQUE INDEX stripe_customers_user_id_idx ON public.stripe_customers USING btree (user_id);


--
-- Name: subscription_events_created_at_idx; Type: INDEX; Schema: public; Owner: -
--

CREATE INDEX subscription_events_created_at_idx ON public.subscription_events USING btree (created_at);


--
-- Name: subscription_events_event_type_idx; Type: INDEX; Schema: public; Owner: -
--

CREATE INDEX subscription_events_event_type_idx ON public.subscription_events USING btree (event_type);


--
-- Name: subscription_events_source_type_idx; Type: INDEX; Schema: public; Owner: -
--

CREATE INDEX subscription_events_source_type_idx ON public.subscription_events USING btree (source_type);


--
-- Name: subscription_events_stripe_event_id_idx; Type: INDEX; Schema: public; Owner: -
--

CREATE INDEX subscription_events_stripe_event_id_idx ON public.subscription_events USING btree (stripe_event_id);


--
-- Name: subscription_events_stripe_event_id_uniq_idx; Type: INDEX; Schema: public; Owner: -
--

CREATE UNIQUE INDEX subscription_events_stripe_event_id_uniq_idx ON public.subscription_events USING btree (stripe_event_id);


--
-- Name: subscription_events_subscription_id_idx; Type: INDEX; Schema: public; Owner: -
--

CREATE INDEX subscription_events_subscription_id_idx ON public.subscription_events USING btree (subscription_id);


--
-- Name: subscription_events_user_id_idx; Type: INDEX; Schema: public; Owner: -
--

CREATE INDEX subscription_events_user_id_idx ON public.subscription_events USING btree (user_id);


--
-- Name: subscriptions_status_idx; Type: INDEX; Schema: public; Owner: -
--

CREATE INDEX subscriptions_status_idx ON public.subscriptions USING btree (status);


--
-- Name: subscriptions_stripe_customer_id_idx; Type: INDEX; Schema: public; Owner: -
--

CREATE INDEX subscriptions_stripe_customer_id_idx ON public.subscriptions USING btree (stripe_customer_id);


--
-- Name: subscriptions_stripe_subscription_id_idx; Type: INDEX; Schema: public; Owner: -
--

CREATE INDEX subscriptions_stripe_subscription_id_idx ON public.subscriptions USING btree (stripe_subscription_id);


--
-- Name: subscriptions_user_id_idx; Type: INDEX; Schema: public; Owner: -
--

CREATE INDEX subscriptions_user_id_idx ON public.subscriptions USING btree (user_id);


--
-- Name: user_roles_app_context_idx; Type: INDEX; Schema: public; Owner: -
--

CREATE INDEX user_roles_app_context_idx ON public.user_roles USING btree (app_context);


--
-- Name: user_roles_granted_by_idx; Type: INDEX; Schema: public; Owner: -
--

CREATE INDEX user_roles_granted_by_idx ON public.user_roles USING btree (granted_by);


--
-- Name: user_roles_is_active_idx; Type: INDEX; Schema: public; Owner: -
--

CREATE INDEX user_roles_is_active_idx ON public.user_roles USING btree (is_active);


--
-- Name: user_roles_role_idx; Type: INDEX; Schema: public; Owner: -
--

CREATE INDEX user_roles_role_idx ON public.user_roles USING btree (role_id);


--
-- Name: user_roles_unique; Type: INDEX; Schema: public; Owner: -
--

CREATE UNIQUE INDEX user_roles_unique ON public.user_roles USING btree (user_id, role_id, app_context);


--
-- Name: user_roles_user_app_active_idx; Type: INDEX; Schema: public; Owner: -
--

CREATE INDEX user_roles_user_app_active_idx ON public.user_roles USING btree (user_id, app_context, is_active);


--
-- Name: user_roles_user_idx; Type: INDEX; Schema: public; Owner: -
--

CREATE INDEX user_roles_user_idx ON public.user_roles USING btree (user_id);


--
-- Name: user_suggestions_app_source_idx; Type: INDEX; Schema: public; Owner: -
--

CREATE INDEX user_suggestions_app_source_idx ON public.user_suggestions USING btree (app_source);


--
-- Name: user_suggestions_created_at_idx; Type: INDEX; Schema: public; Owner: -
--

CREATE INDEX user_suggestions_created_at_idx ON public.user_suggestions USING btree (created_at);


--
-- Name: user_suggestions_entity_slug_idx; Type: INDEX; Schema: public; Owner: -
--

CREATE INDEX user_suggestions_entity_slug_idx ON public.user_suggestions USING btree (entity_slug);


--
-- Name: user_suggestions_entity_type_idx; Type: INDEX; Schema: public; Owner: -
--

CREATE INDEX user_suggestions_entity_type_idx ON public.user_suggestions USING btree (entity_type);


--
-- Name: user_suggestions_status_app_idx; Type: INDEX; Schema: public; Owner: -
--

CREATE INDEX user_suggestions_status_app_idx ON public.user_suggestions USING btree (status, app_source);


--
-- Name: user_suggestions_status_idx; Type: INDEX; Schema: public; Owner: -
--

CREATE INDEX user_suggestions_status_idx ON public.user_suggestions USING btree (status);


--
-- Name: user_suggestions_user_id_idx; Type: INDEX; Schema: public; Owner: -
--

CREATE INDEX user_suggestions_user_id_idx ON public.user_suggestions USING btree (user_id);


--
-- Name: users_active_created_idx; Type: INDEX; Schema: public; Owner: -
--

CREATE INDEX users_active_created_idx ON public.users USING btree (is_active, created_at);


--
-- Name: users_active_idx; Type: INDEX; Schema: public; Owner: -
--

CREATE INDEX users_active_idx ON public.users USING btree (is_active);


--
-- Name: users_auth_user_id_idx; Type: INDEX; Schema: public; Owner: -
--

CREATE UNIQUE INDEX users_auth_user_id_idx ON public.users USING btree (auth_user_id);


--
-- Name: users_created_at_idx; Type: INDEX; Schema: public; Owner: -
--

CREATE INDEX users_created_at_idx ON public.users USING btree (created_at);


--
-- Name: users_deleted_at_idx; Type: INDEX; Schema: public; Owner: -
--

CREATE INDEX users_deleted_at_idx ON public.users USING btree (deleted_at);


--
-- Name: users_email_idx; Type: INDEX; Schema: public; Owner: -
--

CREATE UNIQUE INDEX users_email_idx ON public.users USING btree (email);


--
-- Name: users_last_login_idx; Type: INDEX; Schema: public; Owner: -
--

CREATE INDEX users_last_login_idx ON public.users USING btree (last_login_at);


--
-- Name: vendor_peptides_deleted_at_idx; Type: INDEX; Schema: public; Owner: -
--

CREATE INDEX vendor_peptides_deleted_at_idx ON public.vendor_peptides USING btree (deleted_at);


--
-- Name: vendor_peptides_peptide_idx; Type: INDEX; Schema: public; Owner: -
--

CREATE INDEX vendor_peptides_peptide_idx ON public.vendor_peptides USING btree (peptide_id);


--
-- Name: vendor_peptides_vendor_created_idx; Type: INDEX; Schema: public; Owner: -
--

CREATE INDEX vendor_peptides_vendor_created_idx ON public.vendor_peptides USING btree (vendor_id, created_at);


--
-- Name: vendor_peptides_vendor_idx; Type: INDEX; Schema: public; Owner: -
--

CREATE INDEX vendor_peptides_vendor_idx ON public.vendor_peptides USING btree (vendor_id);


--
-- Name: vendor_peptides_vendor_peptide_idx; Type: INDEX; Schema: public; Owner: -
--

CREATE INDEX vendor_peptides_vendor_peptide_idx ON public.vendor_peptides USING btree (vendor_id, peptide_id);


--
-- Name: vendor_peptides_vendor_peptide_unique; Type: INDEX; Schema: public; Owner: -
--

CREATE UNIQUE INDEX vendor_peptides_vendor_peptide_unique ON public.vendor_peptides USING btree (peptide_id, vendor_id);


--
-- Name: vendors_deleted_at_idx; Type: INDEX; Schema: public; Owner: -
--

CREATE INDEX vendors_deleted_at_idx ON public.vendors USING btree (deleted_at);


--
-- Name: vendors_is_popular_idx; Type: INDEX; Schema: public; Owner: -
--

CREATE INDEX vendors_is_popular_idx ON public.vendors USING btree (is_popular);


--
-- Name: vendors_name_unique_idx; Type: INDEX; Schema: public; Owner: -
--

CREATE UNIQUE INDEX vendors_name_unique_idx ON public.vendors USING btree (lower((name)::text));


--
-- Name: vendors_promo_code_idx; Type: INDEX; Schema: public; Owner: -
--

CREATE INDEX vendors_promo_code_idx ON public.vendors USING btree (promo_code_id);


--
-- Name: vendors_slug_idx; Type: INDEX; Schema: public; Owner: -
--

CREATE INDEX vendors_slug_idx ON public.vendors USING btree (slug);


--
-- Name: vendors_us_vendor_idx; Type: INDEX; Schema: public; Owner: -
--

CREATE INDEX vendors_us_vendor_idx ON public.vendors USING btree (is_us_vendor);


--
-- Name: wiki_copilot_settings_key_uidx; Type: INDEX; Schema: public; Owner: -
--

CREATE UNIQUE INDEX wiki_copilot_settings_key_uidx ON public.wiki_copilot_settings USING btree (key);


--
-- Name: wiki_coupons_active_end_date_idx; Type: INDEX; Schema: public; Owner: -
--

CREATE INDEX wiki_coupons_active_end_date_idx ON public.wiki_coupons USING btree (is_active, end_date);


--
-- Name: wiki_coupons_active_idx; Type: INDEX; Schema: public; Owner: -
--

CREATE INDEX wiki_coupons_active_idx ON public.wiki_coupons USING btree (is_active);


--
-- Name: wiki_coupons_active_usage_idx; Type: INDEX; Schema: public; Owner: -
--

CREATE INDEX wiki_coupons_active_usage_idx ON public.wiki_coupons USING btree (is_active, usage_count);


--
-- Name: wiki_coupons_code_idx; Type: INDEX; Schema: public; Owner: -
--

CREATE UNIQUE INDEX wiki_coupons_code_idx ON public.wiki_coupons USING btree (code);


--
-- Name: wiki_coupons_deleted_at_idx; Type: INDEX; Schema: public; Owner: -
--

CREATE INDEX wiki_coupons_deleted_at_idx ON public.wiki_coupons USING btree (deleted_at);


--
-- Name: wiki_coupons_end_date_idx; Type: INDEX; Schema: public; Owner: -
--

CREATE INDEX wiki_coupons_end_date_idx ON public.wiki_coupons USING btree (end_date);


--
-- Name: wiki_coupons_influencer_idx; Type: INDEX; Schema: public; Owner: -
--

CREATE INDEX wiki_coupons_influencer_idx ON public.wiki_coupons USING btree (influencer_id);


--
-- Name: wiki_coupons_usage_count_idx; Type: INDEX; Schema: public; Owner: -
--

CREATE INDEX wiki_coupons_usage_count_idx ON public.wiki_coupons USING btree (usage_count);


--
-- Name: wiki_coupons_vendor_active_usage_idx; Type: INDEX; Schema: public; Owner: -
--

CREATE INDEX wiki_coupons_vendor_active_usage_idx ON public.wiki_coupons USING btree (vendor_id, is_active, usage_count);


--
-- Name: wiki_coupons_vendor_idx; Type: INDEX; Schema: public; Owner: -
--

CREATE INDEX wiki_coupons_vendor_idx ON public.wiki_coupons USING btree (vendor_id);


--
-- Name: wiki_influencer_analytics_clicks_idx; Type: INDEX; Schema: public; Owner: -
--

CREATE INDEX wiki_influencer_analytics_clicks_idx ON public.wiki_influencer_analytics USING btree (clicks);


--
-- Name: wiki_influencer_analytics_clicks_vendors_idx; Type: INDEX; Schema: public; Owner: -
--

CREATE INDEX wiki_influencer_analytics_clicks_vendors_idx ON public.wiki_influencer_analytics USING btree (clicks_vendors);


--
-- Name: wiki_influencer_analytics_page_views_idx; Type: INDEX; Schema: public; Owner: -
--

CREATE INDEX wiki_influencer_analytics_page_views_idx ON public.wiki_influencer_analytics USING btree (page_views);


--
-- Name: wiki_influencer_analytics_total_activity_idx; Type: INDEX; Schema: public; Owner: -
--

CREATE INDEX wiki_influencer_analytics_total_activity_idx ON public.wiki_influencer_analytics USING btree (clicks, page_views);


--
-- Name: wiki_influencer_analytics_user_idx; Type: INDEX; Schema: public; Owner: -
--

CREATE UNIQUE INDEX wiki_influencer_analytics_user_idx ON public.wiki_influencer_analytics USING btree (user_id);


--
-- Name: wiki_peptide_analytics_action_idx; Type: INDEX; Schema: public; Owner: -
--

CREATE INDEX wiki_peptide_analytics_action_idx ON public.wiki_peptide_analytics USING btree (action);


--
-- Name: wiki_peptide_analytics_ip_address_idx; Type: INDEX; Schema: public; Owner: -
--

CREATE INDEX wiki_peptide_analytics_ip_address_idx ON public.wiki_peptide_analytics USING btree (ip_address);


--
-- Name: wiki_peptide_analytics_peptide_idx; Type: INDEX; Schema: public; Owner: -
--

CREATE INDEX wiki_peptide_analytics_peptide_idx ON public.wiki_peptide_analytics USING btree (peptide_id);


--
-- Name: wiki_peptide_analytics_peptide_timestamp_action_idx; Type: INDEX; Schema: public; Owner: -
--

CREATE INDEX wiki_peptide_analytics_peptide_timestamp_action_idx ON public.wiki_peptide_analytics USING btree (peptide_id, "timestamp" DESC, action);


--
-- Name: wiki_peptide_analytics_timestamp_idx; Type: INDEX; Schema: public; Owner: -
--

CREATE INDEX wiki_peptide_analytics_timestamp_idx ON public.wiki_peptide_analytics USING btree ("timestamp");


--
-- Name: wiki_posts_published_at_idx; Type: INDEX; Schema: public; Owner: -
--

CREATE INDEX wiki_posts_published_at_idx ON public.wiki_posts USING btree (published_at);


--
-- Name: wiki_posts_slug_uidx; Type: INDEX; Schema: public; Owner: -
--

CREATE UNIQUE INDEX wiki_posts_slug_uidx ON public.wiki_posts USING btree (slug);


--
-- Name: wiki_posts_status_idx; Type: INDEX; Schema: public; Owner: -
--

CREATE INDEX wiki_posts_status_idx ON public.wiki_posts USING btree (status);


--
-- Name: wiki_posts_status_published_idx; Type: INDEX; Schema: public; Owner: -
--

CREATE INDEX wiki_posts_status_published_idx ON public.wiki_posts USING btree (status, published_at);


--
-- Name: wiki_referral_banners_active_idx; Type: INDEX; Schema: public; Owner: -
--

CREATE INDEX wiki_referral_banners_active_idx ON public.wiki_referral_banners USING btree (is_active);


--
-- Name: wiki_referral_banners_sort_order_idx; Type: INDEX; Schema: public; Owner: -
--

CREATE INDEX wiki_referral_banners_sort_order_idx ON public.wiki_referral_banners USING btree (sort_order);


--
-- Name: wiki_referral_banners_user_id_idx; Type: INDEX; Schema: public; Owner: -
--

CREATE INDEX wiki_referral_banners_user_id_idx ON public.wiki_referral_banners USING btree (user_id);


--
-- Name: wiki_referral_clicks_action_idx; Type: INDEX; Schema: public; Owner: -
--

CREATE INDEX wiki_referral_clicks_action_idx ON public.wiki_referral_clicks USING btree (action);


--
-- Name: wiki_referral_clicks_referral_code_idx; Type: INDEX; Schema: public; Owner: -
--

CREATE INDEX wiki_referral_clicks_referral_code_idx ON public.wiki_referral_clicks USING btree (referral_code);


--
-- Name: wiki_referral_clicks_timestamp_idx; Type: INDEX; Schema: public; Owner: -
--

CREATE INDEX wiki_referral_clicks_timestamp_idx ON public.wiki_referral_clicks USING btree ("timestamp");


--
-- Name: wiki_referral_clicks_user_idx; Type: INDEX; Schema: public; Owner: -
--

CREATE INDEX wiki_referral_clicks_user_idx ON public.wiki_referral_clicks USING btree (user_id);


--
-- Name: wiki_referral_clicks_user_timestamp_idx; Type: INDEX; Schema: public; Owner: -
--

CREATE INDEX wiki_referral_clicks_user_timestamp_idx ON public.wiki_referral_clicks USING btree (user_id, "timestamp");


--
-- Name: wiki_trending_peptides_peptide_id_idx; Type: INDEX; Schema: public; Owner: -
--

CREATE UNIQUE INDEX wiki_trending_peptides_peptide_id_idx ON public.wiki_trending_peptides USING btree (peptide_id);


--
-- Name: wiki_user_peptide_feedback_answers_answered_at_idx; Type: INDEX; Schema: public; Owner: -
--

CREATE INDEX wiki_user_peptide_feedback_answers_answered_at_idx ON public.wiki_user_peptide_feedback_answers USING btree (answered_at);


--
-- Name: wiki_user_peptide_feedback_answers_feedback_question_idx; Type: INDEX; Schema: public; Owner: -
--

CREATE INDEX wiki_user_peptide_feedback_answers_feedback_question_idx ON public.wiki_user_peptide_feedback_answers USING btree (feedback_question_id);


--
-- Name: wiki_user_peptide_feedback_answers_peptide_idx; Type: INDEX; Schema: public; Owner: -
--

CREATE INDEX wiki_user_peptide_feedback_answers_peptide_idx ON public.wiki_user_peptide_feedback_answers USING btree (peptide_id);


--
-- Name: wiki_user_peptide_feedback_answers_user_idx; Type: INDEX; Schema: public; Owner: -
--

CREATE INDEX wiki_user_peptide_feedback_answers_user_idx ON public.wiki_user_peptide_feedback_answers USING btree (user_id);


--
-- Name: wiki_user_peptide_feedback_answers_user_peptide_feedback_unique; Type: INDEX; Schema: public; Owner: -
--

CREATE UNIQUE INDEX wiki_user_peptide_feedback_answers_user_peptide_feedback_unique ON public.wiki_user_peptide_feedback_answers USING btree (user_id, peptide_id, feedback_question_id);


--
-- Name: wiki_user_peptide_question_answers_answered_at_idx; Type: INDEX; Schema: public; Owner: -
--

CREATE INDEX wiki_user_peptide_question_answers_answered_at_idx ON public.wiki_user_peptide_question_answers USING btree (answered_at);


--
-- Name: wiki_user_peptide_question_answers_option_idx; Type: INDEX; Schema: public; Owner: -
--

CREATE INDEX wiki_user_peptide_question_answers_option_idx ON public.wiki_user_peptide_question_answers USING btree (option_id);


--
-- Name: wiki_user_peptide_question_answers_peptide_idx; Type: INDEX; Schema: public; Owner: -
--

CREATE INDEX wiki_user_peptide_question_answers_peptide_idx ON public.wiki_user_peptide_question_answers USING btree (peptide_id);


--
-- Name: wiki_user_peptide_question_answers_peptide_question_idx; Type: INDEX; Schema: public; Owner: -
--

CREATE INDEX wiki_user_peptide_question_answers_peptide_question_idx ON public.wiki_user_peptide_question_answers USING btree (peptide_id, question_id);


--
-- Name: wiki_user_peptide_question_answers_question_idx; Type: INDEX; Schema: public; Owner: -
--

CREATE INDEX wiki_user_peptide_question_answers_question_idx ON public.wiki_user_peptide_question_answers USING btree (question_id);


--
-- Name: wiki_user_peptide_question_answers_question_option_idx; Type: INDEX; Schema: public; Owner: -
--

CREATE INDEX wiki_user_peptide_question_answers_question_option_idx ON public.wiki_user_peptide_question_answers USING btree (question_id, option_id);


--
-- Name: wiki_user_peptide_question_answers_user_answered_idx; Type: INDEX; Schema: public; Owner: -
--

CREATE INDEX wiki_user_peptide_question_answers_user_answered_idx ON public.wiki_user_peptide_question_answers USING btree (user_id, answered_at DESC);


--
-- Name: wiki_user_peptide_question_answers_user_idx; Type: INDEX; Schema: public; Owner: -
--

CREATE INDEX wiki_user_peptide_question_answers_user_idx ON public.wiki_user_peptide_question_answers USING btree (user_id);


--
-- Name: wiki_user_peptide_question_answers_user_peptide_question_unique; Type: INDEX; Schema: public; Owner: -
--

CREATE UNIQUE INDEX wiki_user_peptide_question_answers_user_peptide_question_unique ON public.wiki_user_peptide_question_answers USING btree (user_id, peptide_id, question_id);


--
-- Name: wiki_user_profiles_influencer_idx; Type: INDEX; Schema: public; Owner: -
--

CREATE INDEX wiki_user_profiles_influencer_idx ON public.wiki_user_profiles USING btree (is_influencer);


--
-- Name: wiki_user_profiles_referral_code_idx; Type: INDEX; Schema: public; Owner: -
--

CREATE INDEX wiki_user_profiles_referral_code_idx ON public.wiki_user_profiles USING btree (referral_code);


--
-- Name: wiki_user_profiles_user_id_idx; Type: INDEX; Schema: public; Owner: -
--

CREATE UNIQUE INDEX wiki_user_profiles_user_id_idx ON public.wiki_user_profiles USING btree (user_id);


--
-- Name: app_credit_costs app_credit_costs_set_updated_at; Type: TRIGGER; Schema: public; Owner: -
--

CREATE TRIGGER app_credit_costs_set_updated_at BEFORE UPDATE ON public.app_credit_costs FOR EACH ROW EXECUTE FUNCTION public.set_updated_at();


--
-- Name: credit_accounts credit_accounts_set_updated_at; Type: TRIGGER; Schema: public; Owner: -
--

CREATE TRIGGER credit_accounts_set_updated_at BEFORE UPDATE ON public.credit_accounts FOR EACH ROW EXECUTE FUNCTION public.set_updated_at();


--
-- Name: credit_packages credit_packages_set_updated_at; Type: TRIGGER; Schema: public; Owner: -
--

CREATE TRIGGER credit_packages_set_updated_at BEFORE UPDATE ON public.credit_packages FOR EACH ROW EXECUTE FUNCTION public.set_updated_at();


--
-- Name: stripe_customers stripe_customers_set_updated_at; Type: TRIGGER; Schema: public; Owner: -
--

CREATE TRIGGER stripe_customers_set_updated_at BEFORE UPDATE ON public.stripe_customers FOR EACH ROW EXECUTE FUNCTION public.set_updated_at();


--
-- Name: app_credit_costs app_credit_costs_app_source_fk; Type: FK CONSTRAINT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.app_credit_costs
    ADD CONSTRAINT app_credit_costs_app_source_fk FOREIGN KEY (app_source) REFERENCES public.app_sources(code) ON UPDATE CASCADE;


--
-- Name: calc_notification_devices calc_notification_devices_notification_id_calc_notifications_id; Type: FK CONSTRAINT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.calc_notification_devices
    ADD CONSTRAINT calc_notification_devices_notification_id_calc_notifications_id FOREIGN KEY (notification_id) REFERENCES public.calc_notifications(id) ON UPDATE CASCADE ON DELETE CASCADE;


--
-- Name: calc_notification_devices calc_notification_devices_user_device_id_calc_user_devices_id_f; Type: FK CONSTRAINT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.calc_notification_devices
    ADD CONSTRAINT calc_notification_devices_user_device_id_calc_user_devices_id_f FOREIGN KEY (user_device_id) REFERENCES public.calc_user_devices(id) ON UPDATE CASCADE ON DELETE CASCADE;


--
-- Name: calc_notifications calc_notifications_user_id_users_id_fk; Type: FK CONSTRAINT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.calc_notifications
    ADD CONSTRAINT calc_notifications_user_id_users_id_fk FOREIGN KEY (user_id) REFERENCES public.users(id) ON UPDATE CASCADE ON DELETE CASCADE;


--
-- Name: calc_promo_banners calc_promo_banners_created_by_users_id_fk; Type: FK CONSTRAINT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.calc_promo_banners
    ADD CONSTRAINT calc_promo_banners_created_by_users_id_fk FOREIGN KEY (created_by) REFERENCES public.users(id) ON UPDATE CASCADE ON DELETE SET NULL;


--
-- Name: calc_user_devices calc_user_devices_user_id_users_id_fk; Type: FK CONSTRAINT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.calc_user_devices
    ADD CONSTRAINT calc_user_devices_user_id_users_id_fk FOREIGN KEY (user_id) REFERENCES public.users(id) ON UPDATE CASCADE ON DELETE CASCADE;


--
-- Name: calc_user_profiles calc_user_profiles_user_id_users_id_fk; Type: FK CONSTRAINT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.calc_user_profiles
    ADD CONSTRAINT calc_user_profiles_user_id_users_id_fk FOREIGN KEY (user_id) REFERENCES public.users(id) ON UPDATE CASCADE ON DELETE CASCADE;


--
-- Name: calc_user_reviews calc_user_reviews_user_id_users_id_fk; Type: FK CONSTRAINT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.calc_user_reviews
    ADD CONSTRAINT calc_user_reviews_user_id_users_id_fk FOREIGN KEY (user_id) REFERENCES public.users(id) ON UPDATE CASCADE ON DELETE CASCADE;


--
-- Name: calc_vials calc_vials_user_id_users_id_fk; Type: FK CONSTRAINT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.calc_vials
    ADD CONSTRAINT calc_vials_user_id_users_id_fk FOREIGN KEY (user_id) REFERENCES public.users(id) ON UPDATE CASCADE ON DELETE CASCADE;


--
-- Name: categories categories_parent_category_id_categories_id_fk; Type: FK CONSTRAINT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.categories
    ADD CONSTRAINT categories_parent_category_id_categories_id_fk FOREIGN KEY (parent_category_id) REFERENCES public.categories(id) ON UPDATE CASCADE ON DELETE SET NULL;


--
-- Name: credit_accounts credit_accounts_user_id_fkey; Type: FK CONSTRAINT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.credit_accounts
    ADD CONSTRAINT credit_accounts_user_id_fkey FOREIGN KEY (user_id) REFERENCES public.users(id) ON DELETE CASCADE;


--
-- Name: credit_packages credit_packages_app_source_fkey; Type: FK CONSTRAINT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.credit_packages
    ADD CONSTRAINT credit_packages_app_source_fkey FOREIGN KEY (app_source) REFERENCES public.app_sources(code) ON UPDATE CASCADE ON DELETE SET NULL;


--
-- Name: credit_transactions credit_transactions_app_source_fk; Type: FK CONSTRAINT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.credit_transactions
    ADD CONSTRAINT credit_transactions_app_source_fk FOREIGN KEY (app_source) REFERENCES public.app_sources(code) ON UPDATE CASCADE;


--
-- Name: credit_transactions credit_transactions_credit_account_id_fkey; Type: FK CONSTRAINT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.credit_transactions
    ADD CONSTRAINT credit_transactions_credit_account_id_fkey FOREIGN KEY (credit_account_id) REFERENCES public.credit_accounts(id) ON DELETE SET NULL;


--
-- Name: credit_transactions credit_transactions_credit_package_id_fkey; Type: FK CONSTRAINT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.credit_transactions
    ADD CONSTRAINT credit_transactions_credit_package_id_fkey FOREIGN KEY (credit_package_id) REFERENCES public.credit_packages(id) ON DELETE SET NULL;


--
-- Name: credit_transactions credit_transactions_user_id_fkey; Type: FK CONSTRAINT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.credit_transactions
    ADD CONSTRAINT credit_transactions_user_id_fkey FOREIGN KEY (user_id) REFERENCES public.users(id) ON DELETE CASCADE;


--
-- Name: influencer_profiles influencer_profiles_user_id_users_id_fk; Type: FK CONSTRAINT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.influencer_profiles
    ADD CONSTRAINT influencer_profiles_user_id_users_id_fk FOREIGN KEY (user_id) REFERENCES public.users(id) ON DELETE CASCADE;


--
-- Name: pepti_price_notifications pepti_price_notifications_user_id_users_id_fk; Type: FK CONSTRAINT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.pepti_price_notifications
    ADD CONSTRAINT pepti_price_notifications_user_id_users_id_fk FOREIGN KEY (user_id) REFERENCES public.users(id) ON DELETE CASCADE;


--
-- Name: pepti_price_price_history pepti_price_price_history_administration_method_id_administrati; Type: FK CONSTRAINT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.pepti_price_price_history
    ADD CONSTRAINT pepti_price_price_history_administration_method_id_administrati FOREIGN KEY (administration_method_id) REFERENCES public.administration_methods(id) ON UPDATE CASCADE ON DELETE CASCADE;


--
-- Name: pepti_price_price_history pepti_price_price_history_dosage_id_dosages_id_fk; Type: FK CONSTRAINT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.pepti_price_price_history
    ADD CONSTRAINT pepti_price_price_history_dosage_id_dosages_id_fk FOREIGN KEY (dosage_id) REFERENCES public.dosages(id) ON UPDATE CASCADE ON DELETE RESTRICT;


--
-- Name: pepti_price_price_history pepti_price_price_history_peptide_id_peptides_id_fk; Type: FK CONSTRAINT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.pepti_price_price_history
    ADD CONSTRAINT pepti_price_price_history_peptide_id_peptides_id_fk FOREIGN KEY (peptide_id) REFERENCES public.peptides(id) ON UPDATE CASCADE ON DELETE CASCADE;


--
-- Name: pepti_price_price_history pepti_price_price_history_vendor_id_vendors_id_fk; Type: FK CONSTRAINT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.pepti_price_price_history
    ADD CONSTRAINT pepti_price_price_history_vendor_id_vendors_id_fk FOREIGN KEY (vendor_id) REFERENCES public.vendors(id) ON UPDATE CASCADE ON DELETE CASCADE;


--
-- Name: pepti_price_vendor_pricing pepti_price_vendor_pricing_administration_method_id_administrat; Type: FK CONSTRAINT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.pepti_price_vendor_pricing
    ADD CONSTRAINT pepti_price_vendor_pricing_administration_method_id_administrat FOREIGN KEY (administration_method_id) REFERENCES public.administration_methods(id) ON UPDATE CASCADE ON DELETE CASCADE;


--
-- Name: pepti_price_vendor_pricing pepti_price_vendor_pricing_dosage_id_dosages_id_fk; Type: FK CONSTRAINT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.pepti_price_vendor_pricing
    ADD CONSTRAINT pepti_price_vendor_pricing_dosage_id_dosages_id_fk FOREIGN KEY (dosage_id) REFERENCES public.dosages(id) ON UPDATE CASCADE ON DELETE RESTRICT;


--
-- Name: pepti_price_vendor_pricing pepti_price_vendor_pricing_peptide_id_peptides_id_fk; Type: FK CONSTRAINT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.pepti_price_vendor_pricing
    ADD CONSTRAINT pepti_price_vendor_pricing_peptide_id_peptides_id_fk FOREIGN KEY (peptide_id) REFERENCES public.peptides(id) ON UPDATE CASCADE ON DELETE CASCADE;


--
-- Name: pepti_price_vendor_pricing pepti_price_vendor_pricing_promo_code_id_pepti_price_promo_code; Type: FK CONSTRAINT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.pepti_price_vendor_pricing
    ADD CONSTRAINT pepti_price_vendor_pricing_promo_code_id_pepti_price_promo_code FOREIGN KEY (promo_code_id) REFERENCES public.pepti_price_promo_codes(id) ON UPDATE CASCADE ON DELETE SET NULL;


--
-- Name: pepti_price_vendor_pricing pepti_price_vendor_pricing_vendor_id_vendors_id_fk; Type: FK CONSTRAINT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.pepti_price_vendor_pricing
    ADD CONSTRAINT pepti_price_vendor_pricing_vendor_id_vendors_id_fk FOREIGN KEY (vendor_id) REFERENCES public.vendors(id) ON UPDATE CASCADE ON DELETE CASCADE;


--
-- Name: pepti_price_watchlist pepti_price_watchlist_peptide_id_peptides_id_fk; Type: FK CONSTRAINT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.pepti_price_watchlist
    ADD CONSTRAINT pepti_price_watchlist_peptide_id_peptides_id_fk FOREIGN KEY (peptide_id) REFERENCES public.peptides(id) ON DELETE CASCADE;


--
-- Name: pepti_price_watchlist pepti_price_watchlist_user_id_users_id_fk; Type: FK CONSTRAINT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.pepti_price_watchlist
    ADD CONSTRAINT pepti_price_watchlist_user_id_users_id_fk FOREIGN KEY (user_id) REFERENCES public.users(id) ON DELETE CASCADE;


--
-- Name: peptide_benefits peptide_benefits_benefit_id_benefits_id_fk; Type: FK CONSTRAINT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.peptide_benefits
    ADD CONSTRAINT peptide_benefits_benefit_id_benefits_id_fk FOREIGN KEY (benefit_id) REFERENCES public.benefits(id) ON UPDATE CASCADE ON DELETE RESTRICT;


--
-- Name: peptide_benefits peptide_benefits_peptide_id_peptides_id_fk; Type: FK CONSTRAINT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.peptide_benefits
    ADD CONSTRAINT peptide_benefits_peptide_id_peptides_id_fk FOREIGN KEY (peptide_id) REFERENCES public.peptides(id) ON UPDATE CASCADE ON DELETE RESTRICT;


--
-- Name: peptide_interactions peptide_interactions_peptide_id_1_peptides_id_fk; Type: FK CONSTRAINT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.peptide_interactions
    ADD CONSTRAINT peptide_interactions_peptide_id_1_peptides_id_fk FOREIGN KEY (peptide_id_1) REFERENCES public.peptides(id) ON UPDATE CASCADE ON DELETE RESTRICT;


--
-- Name: peptide_interactions peptide_interactions_peptide_id_2_peptides_id_fk; Type: FK CONSTRAINT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.peptide_interactions
    ADD CONSTRAINT peptide_interactions_peptide_id_2_peptides_id_fk FOREIGN KEY (peptide_id_2) REFERENCES public.peptides(id) ON UPDATE CASCADE ON DELETE RESTRICT;


--
-- Name: peptide_protocol_reconstitution_steps peptide_protocol_reconstitution_steps_protocol_id_peptide_proto; Type: FK CONSTRAINT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.peptide_protocol_reconstitution_steps
    ADD CONSTRAINT peptide_protocol_reconstitution_steps_protocol_id_peptide_proto FOREIGN KEY (protocol_id) REFERENCES public.peptide_protocols(id) ON UPDATE CASCADE ON DELETE CASCADE;


--
-- Name: peptide_protocols peptide_protocols_administration_method_id_administration_metho; Type: FK CONSTRAINT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.peptide_protocols
    ADD CONSTRAINT peptide_protocols_administration_method_id_administration_metho FOREIGN KEY (administration_method_id) REFERENCES public.administration_methods(id) ON UPDATE CASCADE ON DELETE RESTRICT;


--
-- Name: peptide_protocols peptide_protocols_peptide_id_peptides_id_fk; Type: FK CONSTRAINT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.peptide_protocols
    ADD CONSTRAINT peptide_protocols_peptide_id_peptides_id_fk FOREIGN KEY (peptide_id) REFERENCES public.peptides(id) ON UPDATE CASCADE ON DELETE RESTRICT;


--
-- Name: peptide_references peptide_references_citation_id_citations_id_fk; Type: FK CONSTRAINT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.peptide_references
    ADD CONSTRAINT peptide_references_citation_id_citations_id_fk FOREIGN KEY (citation_id) REFERENCES public.citations(id) ON UPDATE CASCADE ON DELETE RESTRICT;


--
-- Name: peptide_references peptide_references_peptide_id_peptides_id_fk; Type: FK CONSTRAINT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.peptide_references
    ADD CONSTRAINT peptide_references_peptide_id_peptides_id_fk FOREIGN KEY (peptide_id) REFERENCES public.peptides(id) ON UPDATE CASCADE ON DELETE RESTRICT;


--
-- Name: peptide_references peptide_references_study_id_research_studies_id_fk; Type: FK CONSTRAINT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.peptide_references
    ADD CONSTRAINT peptide_references_study_id_research_studies_id_fk FOREIGN KEY (study_id) REFERENCES public.research_studies(id) ON UPDATE CASCADE ON DELETE RESTRICT;


--
-- Name: peptide_research_indication_studies peptide_research_indication_studies_indication_id_peptide_resea; Type: FK CONSTRAINT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.peptide_research_indication_studies
    ADD CONSTRAINT peptide_research_indication_studies_indication_id_peptide_resea FOREIGN KEY (indication_id) REFERENCES public.peptide_research_indications(id) ON UPDATE CASCADE ON DELETE CASCADE;


--
-- Name: peptide_research_indication_studies peptide_research_indication_studies_protocol_id_peptide_protoco; Type: FK CONSTRAINT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.peptide_research_indication_studies
    ADD CONSTRAINT peptide_research_indication_studies_protocol_id_peptide_protoco FOREIGN KEY (protocol_id) REFERENCES public.peptide_protocols(id) ON UPDATE CASCADE ON DELETE CASCADE;


--
-- Name: peptide_research_indications peptide_research_indications_peptide_id_peptides_id_fk; Type: FK CONSTRAINT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.peptide_research_indications
    ADD CONSTRAINT peptide_research_indications_peptide_id_peptides_id_fk FOREIGN KEY (peptide_id) REFERENCES public.peptides(id) ON UPDATE CASCADE ON DELETE CASCADE;


--
-- Name: peptide_side_effects peptide_side_effects_peptide_id_peptides_id_fk; Type: FK CONSTRAINT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.peptide_side_effects
    ADD CONSTRAINT peptide_side_effects_peptide_id_peptides_id_fk FOREIGN KEY (peptide_id) REFERENCES public.peptides(id) ON UPDATE CASCADE ON DELETE RESTRICT;


--
-- Name: peptide_side_effects peptide_side_effects_side_effect_id_side_effects_id_fk; Type: FK CONSTRAINT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.peptide_side_effects
    ADD CONSTRAINT peptide_side_effects_side_effect_id_side_effects_id_fk FOREIGN KEY (side_effect_id) REFERENCES public.side_effects(id) ON UPDATE CASCADE ON DELETE RESTRICT;


--
-- Name: peptides peptides_category_id_categories_id_fk; Type: FK CONSTRAINT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.peptides
    ADD CONSTRAINT peptides_category_id_categories_id_fk FOREIGN KEY (category_id) REFERENCES public.categories(id) ON UPDATE CASCADE ON DELETE SET NULL;


--
-- Name: protocol_application_places protocol_application_places_application_place_id_application_pl; Type: FK CONSTRAINT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.protocol_application_places
    ADD CONSTRAINT protocol_application_places_application_place_id_application_pl FOREIGN KEY (application_place_id) REFERENCES public.application_places(id) ON UPDATE CASCADE ON DELETE CASCADE;


--
-- Name: protocol_application_places protocol_application_places_protocol_id_peptide_protocols_id_fk; Type: FK CONSTRAINT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.protocol_application_places
    ADD CONSTRAINT protocol_application_places_protocol_id_peptide_protocols_id_fk FOREIGN KEY (protocol_id) REFERENCES public.peptide_protocols(id) ON UPDATE CASCADE ON DELETE CASCADE;


--
-- Name: protocol_dosage_benefits protocol_dosage_benefits_benefit_id_benefits_id_fk; Type: FK CONSTRAINT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.protocol_dosage_benefits
    ADD CONSTRAINT protocol_dosage_benefits_benefit_id_benefits_id_fk FOREIGN KEY (benefit_id) REFERENCES public.benefits(id) ON UPDATE CASCADE ON DELETE RESTRICT;


--
-- Name: protocol_dosage_benefits protocol_dosage_benefits_protocol_dosage_id_protocol_dosages_id; Type: FK CONSTRAINT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.protocol_dosage_benefits
    ADD CONSTRAINT protocol_dosage_benefits_protocol_dosage_id_protocol_dosages_id FOREIGN KEY (protocol_dosage_id) REFERENCES public.protocol_dosages(id) ON UPDATE CASCADE ON DELETE CASCADE;


--
-- Name: protocol_dosage_side_effects protocol_dosage_side_effects_protocol_dosage_id_protocol_dosage; Type: FK CONSTRAINT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.protocol_dosage_side_effects
    ADD CONSTRAINT protocol_dosage_side_effects_protocol_dosage_id_protocol_dosage FOREIGN KEY (protocol_dosage_id) REFERENCES public.protocol_dosages(id) ON UPDATE CASCADE ON DELETE CASCADE;


--
-- Name: protocol_dosage_side_effects protocol_dosage_side_effects_side_effect_id_side_effects_id_fk; Type: FK CONSTRAINT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.protocol_dosage_side_effects
    ADD CONSTRAINT protocol_dosage_side_effects_side_effect_id_side_effects_id_fk FOREIGN KEY (side_effect_id) REFERENCES public.side_effects(id) ON UPDATE CASCADE ON DELETE RESTRICT;


--
-- Name: protocol_dosages protocol_dosages_dosage_id_dosages_id_fk; Type: FK CONSTRAINT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.protocol_dosages
    ADD CONSTRAINT protocol_dosages_dosage_id_dosages_id_fk FOREIGN KEY (dosage_id) REFERENCES public.dosages(id) ON UPDATE CASCADE ON DELETE RESTRICT;


--
-- Name: protocol_dosages protocol_dosages_protocol_id_peptide_protocols_id_fk; Type: FK CONSTRAINT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.protocol_dosages
    ADD CONSTRAINT protocol_dosages_protocol_id_peptide_protocols_id_fk FOREIGN KEY (protocol_id) REFERENCES public.peptide_protocols(id) ON UPDATE CASCADE ON DELETE CASCADE;


--
-- Name: protocol_dosages protocol_dosages_schedule_id_schedules_id_fk; Type: FK CONSTRAINT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.protocol_dosages
    ADD CONSTRAINT protocol_dosages_schedule_id_schedules_id_fk FOREIGN KEY (schedule_id) REFERENCES public.schedules(id) ON UPDATE CASCADE ON DELETE RESTRICT;


--
-- Name: protocol_quality_indicators protocol_quality_indicators_protocol_id_peptide_protocols_id_fk; Type: FK CONSTRAINT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.protocol_quality_indicators
    ADD CONSTRAINT protocol_quality_indicators_protocol_id_peptide_protocols_id_fk FOREIGN KEY (protocol_id) REFERENCES public.peptide_protocols(id) ON UPDATE CASCADE ON DELETE CASCADE;


--
-- Name: sds_compounds sds_compounds_peptide_id_peptides_id_fk; Type: FK CONSTRAINT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.sds_compounds
    ADD CONSTRAINT sds_compounds_peptide_id_peptides_id_fk FOREIGN KEY (peptide_id) REFERENCES public.peptides(id) ON UPDATE CASCADE ON DELETE SET NULL;


--
-- Name: sds_documents sds_documents_compound_id_sds_compounds_id_fk; Type: FK CONSTRAINT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.sds_documents
    ADD CONSTRAINT sds_documents_compound_id_sds_compounds_id_fk FOREIGN KEY (compound_id) REFERENCES public.sds_compounds(id) ON DELETE SET NULL;


--
-- Name: sds_documents sds_documents_user_id_users_id_fk; Type: FK CONSTRAINT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.sds_documents
    ADD CONSTRAINT sds_documents_user_id_users_id_fk FOREIGN KEY (user_id) REFERENCES public.users(id) ON DELETE SET NULL;


--
-- Name: sds_hazard_data sds_hazard_data_compound_id_sds_compounds_id_fk; Type: FK CONSTRAINT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.sds_hazard_data
    ADD CONSTRAINT sds_hazard_data_compound_id_sds_compounds_id_fk FOREIGN KEY (compound_id) REFERENCES public.sds_compounds(id) ON DELETE CASCADE;


--
-- Name: sds_job_queue sds_job_queue_compound_id_sds_compounds_id_fk; Type: FK CONSTRAINT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.sds_job_queue
    ADD CONSTRAINT sds_job_queue_compound_id_sds_compounds_id_fk FOREIGN KEY (compound_id) REFERENCES public.sds_compounds(id) ON DELETE SET NULL;


--
-- Name: sds_job_queue sds_job_queue_user_id_fkey; Type: FK CONSTRAINT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.sds_job_queue
    ADD CONSTRAINT sds_job_queue_user_id_fkey FOREIGN KEY (user_id) REFERENCES auth.users(id) ON DELETE SET NULL;


--
-- Name: sds_pinned_compounds sds_pinned_compounds_compound_id_sds_compounds_id_fk; Type: FK CONSTRAINT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.sds_pinned_compounds
    ADD CONSTRAINT sds_pinned_compounds_compound_id_sds_compounds_id_fk FOREIGN KEY (compound_id) REFERENCES public.sds_compounds(id) ON DELETE SET NULL;


--
-- Name: sds_sections sds_sections_compound_id_sds_compounds_id_fk; Type: FK CONSTRAINT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.sds_sections
    ADD CONSTRAINT sds_sections_compound_id_sds_compounds_id_fk FOREIGN KEY (compound_id) REFERENCES public.sds_compounds(id) ON DELETE CASCADE;


--
-- Name: stripe_customers stripe_customers_user_id_fkey; Type: FK CONSTRAINT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.stripe_customers
    ADD CONSTRAINT stripe_customers_user_id_fkey FOREIGN KEY (user_id) REFERENCES public.users(id) ON DELETE CASCADE;


--
-- Name: subscription_events subscription_events_subscription_id_fkey; Type: FK CONSTRAINT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.subscription_events
    ADD CONSTRAINT subscription_events_subscription_id_fkey FOREIGN KEY (subscription_id) REFERENCES public.subscriptions(id) ON DELETE SET NULL;


--
-- Name: subscription_events subscription_events_user_id_fkey; Type: FK CONSTRAINT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.subscription_events
    ADD CONSTRAINT subscription_events_user_id_fkey FOREIGN KEY (user_id) REFERENCES public.users(id) ON DELETE SET NULL;


--
-- Name: subscriptions subscriptions_user_id_fkey; Type: FK CONSTRAINT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.subscriptions
    ADD CONSTRAINT subscriptions_user_id_fkey FOREIGN KEY (user_id) REFERENCES public.users(id) ON DELETE CASCADE;


--
-- Name: user_roles user_roles_granted_by_users_id_fk; Type: FK CONSTRAINT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.user_roles
    ADD CONSTRAINT user_roles_granted_by_users_id_fk FOREIGN KEY (granted_by) REFERENCES public.users(id);


--
-- Name: user_roles user_roles_role_id_roles_id_fk; Type: FK CONSTRAINT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.user_roles
    ADD CONSTRAINT user_roles_role_id_roles_id_fk FOREIGN KEY (role_id) REFERENCES public.roles(id) ON DELETE CASCADE;


--
-- Name: user_roles user_roles_user_id_users_id_fk; Type: FK CONSTRAINT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.user_roles
    ADD CONSTRAINT user_roles_user_id_users_id_fk FOREIGN KEY (user_id) REFERENCES public.users(id) ON DELETE CASCADE;


--
-- Name: user_suggestions user_suggestions_app_source_fk; Type: FK CONSTRAINT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.user_suggestions
    ADD CONSTRAINT user_suggestions_app_source_fk FOREIGN KEY (app_source) REFERENCES public.app_sources(code) ON UPDATE CASCADE;


--
-- Name: user_suggestions user_suggestions_reviewed_by_users_id_fk; Type: FK CONSTRAINT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.user_suggestions
    ADD CONSTRAINT user_suggestions_reviewed_by_users_id_fk FOREIGN KEY (reviewed_by) REFERENCES public.users(id) ON UPDATE CASCADE ON DELETE SET NULL;


--
-- Name: user_suggestions user_suggestions_user_id_users_id_fk; Type: FK CONSTRAINT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.user_suggestions
    ADD CONSTRAINT user_suggestions_user_id_users_id_fk FOREIGN KEY (user_id) REFERENCES public.users(id) ON UPDATE CASCADE ON DELETE SET NULL;


--
-- Name: vendor_peptides vendor_peptides_peptide_id_peptides_id_fk; Type: FK CONSTRAINT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.vendor_peptides
    ADD CONSTRAINT vendor_peptides_peptide_id_peptides_id_fk FOREIGN KEY (peptide_id) REFERENCES public.peptides(id) ON UPDATE CASCADE ON DELETE CASCADE;


--
-- Name: vendor_peptides vendor_peptides_vendor_id_vendors_id_fk; Type: FK CONSTRAINT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.vendor_peptides
    ADD CONSTRAINT vendor_peptides_vendor_id_vendors_id_fk FOREIGN KEY (vendor_id) REFERENCES public.vendors(id) ON UPDATE CASCADE ON DELETE CASCADE;


--
-- Name: vendors vendors_promo_code_id_pepti_price_promo_codes_id_fk; Type: FK CONSTRAINT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.vendors
    ADD CONSTRAINT vendors_promo_code_id_pepti_price_promo_codes_id_fk FOREIGN KEY (promo_code_id) REFERENCES public.pepti_price_promo_codes(id) ON DELETE SET NULL;


--
-- Name: wiki_coupons wiki_coupons_influencer_id_users_id_fk; Type: FK CONSTRAINT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.wiki_coupons
    ADD CONSTRAINT wiki_coupons_influencer_id_users_id_fk FOREIGN KEY (influencer_id) REFERENCES public.users(id) ON UPDATE CASCADE ON DELETE SET NULL;


--
-- Name: wiki_coupons wiki_coupons_vendor_id_vendors_id_fk; Type: FK CONSTRAINT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.wiki_coupons
    ADD CONSTRAINT wiki_coupons_vendor_id_vendors_id_fk FOREIGN KEY (vendor_id) REFERENCES public.vendors(id) ON UPDATE CASCADE ON DELETE SET NULL;


--
-- Name: wiki_influencer_analytics wiki_influencer_analytics_user_id_users_id_fk; Type: FK CONSTRAINT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.wiki_influencer_analytics
    ADD CONSTRAINT wiki_influencer_analytics_user_id_users_id_fk FOREIGN KEY (user_id) REFERENCES public.users(id) ON UPDATE CASCADE ON DELETE CASCADE;


--
-- Name: wiki_peptide_analytics wiki_peptide_analytics_peptide_id_peptides_id_fk; Type: FK CONSTRAINT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.wiki_peptide_analytics
    ADD CONSTRAINT wiki_peptide_analytics_peptide_id_peptides_id_fk FOREIGN KEY (peptide_id) REFERENCES public.peptides(id) ON UPDATE CASCADE ON DELETE SET NULL;


--
-- Name: wiki_referral_banners wiki_referral_banners_user_id_users_id_fk; Type: FK CONSTRAINT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.wiki_referral_banners
    ADD CONSTRAINT wiki_referral_banners_user_id_users_id_fk FOREIGN KEY (user_id) REFERENCES public.users(id) ON UPDATE CASCADE ON DELETE CASCADE;


--
-- Name: wiki_referral_clicks wiki_referral_clicks_peptide_id_peptides_id_fk; Type: FK CONSTRAINT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.wiki_referral_clicks
    ADD CONSTRAINT wiki_referral_clicks_peptide_id_peptides_id_fk FOREIGN KEY (peptide_id) REFERENCES public.peptides(id) ON UPDATE CASCADE ON DELETE SET NULL;


--
-- Name: wiki_referral_clicks wiki_referral_clicks_user_id_users_id_fk; Type: FK CONSTRAINT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.wiki_referral_clicks
    ADD CONSTRAINT wiki_referral_clicks_user_id_users_id_fk FOREIGN KEY (user_id) REFERENCES public.users(id) ON UPDATE CASCADE ON DELETE CASCADE;


--
-- Name: wiki_referral_clicks wiki_referral_clicks_vendor_id_vendors_id_fk; Type: FK CONSTRAINT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.wiki_referral_clicks
    ADD CONSTRAINT wiki_referral_clicks_vendor_id_vendors_id_fk FOREIGN KEY (vendor_id) REFERENCES public.vendors(id) ON UPDATE CASCADE ON DELETE SET NULL;


--
-- Name: wiki_trending_peptides wiki_trending_peptides_peptide_id_peptides_id_fk; Type: FK CONSTRAINT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.wiki_trending_peptides
    ADD CONSTRAINT wiki_trending_peptides_peptide_id_peptides_id_fk FOREIGN KEY (peptide_id) REFERENCES public.peptides(id) ON UPDATE CASCADE ON DELETE CASCADE;


--
-- Name: wiki_user_peptide_feedback_answers wiki_user_peptide_feedback_answers_feedback_question_id_feedbac; Type: FK CONSTRAINT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.wiki_user_peptide_feedback_answers
    ADD CONSTRAINT wiki_user_peptide_feedback_answers_feedback_question_id_feedbac FOREIGN KEY (feedback_question_id) REFERENCES public.feedback_questions(id) ON UPDATE CASCADE ON DELETE RESTRICT;


--
-- Name: wiki_user_peptide_feedback_answers wiki_user_peptide_feedback_answers_peptide_id_peptides_id_fk; Type: FK CONSTRAINT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.wiki_user_peptide_feedback_answers
    ADD CONSTRAINT wiki_user_peptide_feedback_answers_peptide_id_peptides_id_fk FOREIGN KEY (peptide_id) REFERENCES public.peptides(id) ON UPDATE CASCADE ON DELETE SET NULL;


--
-- Name: wiki_user_peptide_feedback_answers wiki_user_peptide_feedback_answers_user_id_users_id_fk; Type: FK CONSTRAINT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.wiki_user_peptide_feedback_answers
    ADD CONSTRAINT wiki_user_peptide_feedback_answers_user_id_users_id_fk FOREIGN KEY (user_id) REFERENCES public.users(id) ON DELETE CASCADE;


--
-- Name: wiki_user_peptide_question_answers wiki_user_peptide_question_answers_option_id_peptide_question_o; Type: FK CONSTRAINT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.wiki_user_peptide_question_answers
    ADD CONSTRAINT wiki_user_peptide_question_answers_option_id_peptide_question_o FOREIGN KEY (option_id) REFERENCES public.peptide_question_options(id) ON UPDATE CASCADE ON DELETE RESTRICT;


--
-- Name: wiki_user_peptide_question_answers wiki_user_peptide_question_answers_peptide_id_peptides_id_fk; Type: FK CONSTRAINT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.wiki_user_peptide_question_answers
    ADD CONSTRAINT wiki_user_peptide_question_answers_peptide_id_peptides_id_fk FOREIGN KEY (peptide_id) REFERENCES public.peptides(id) ON UPDATE CASCADE ON DELETE SET NULL;


--
-- Name: wiki_user_peptide_question_answers wiki_user_peptide_question_answers_question_id_peptide_question; Type: FK CONSTRAINT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.wiki_user_peptide_question_answers
    ADD CONSTRAINT wiki_user_peptide_question_answers_question_id_peptide_question FOREIGN KEY (question_id) REFERENCES public.peptide_questions(id) ON UPDATE CASCADE ON DELETE RESTRICT;


--
-- Name: wiki_user_peptide_question_answers wiki_user_peptide_question_answers_user_id_users_id_fk; Type: FK CONSTRAINT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.wiki_user_peptide_question_answers
    ADD CONSTRAINT wiki_user_peptide_question_answers_user_id_users_id_fk FOREIGN KEY (user_id) REFERENCES public.users(id) ON DELETE CASCADE;


--
-- Name: wiki_user_profiles wiki_user_profiles_user_id_users_id_fk; Type: FK CONSTRAINT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.wiki_user_profiles
    ADD CONSTRAINT wiki_user_profiles_user_id_users_id_fk FOREIGN KEY (user_id) REFERENCES public.users(id) ON DELETE CASCADE;


--
-- Name: roles Allow auth admin to read roles; Type: POLICY; Schema: public; Owner: -
--

CREATE POLICY "Allow auth admin to read roles" ON public.roles FOR SELECT TO supabase_auth_admin USING (true);


--
-- Name: user_roles Allow auth admin to read user roles; Type: POLICY; Schema: public; Owner: -
--

CREATE POLICY "Allow auth admin to read user roles" ON public.user_roles FOR SELECT TO supabase_auth_admin USING (true);


--
-- Name: users Allow auth admin to read users; Type: POLICY; Schema: public; Owner: -
--

CREATE POLICY "Allow auth admin to read users" ON public.users FOR SELECT TO supabase_auth_admin USING (true);


--
-- Name: app_credit_costs; Type: ROW SECURITY; Schema: public; Owner: -
--

ALTER TABLE public.app_credit_costs ENABLE ROW LEVEL SECURITY;

--
-- Name: app_credit_costs app_credit_costs_admin_all; Type: POLICY; Schema: public; Owner: -
--

CREATE POLICY app_credit_costs_admin_all ON public.app_credit_costs TO authenticated USING ((((( SELECT auth.jwt() AS jwt) -> 'app_metadata'::text) ->> 'role'::text) = 'admin'::text)) WITH CHECK ((((( SELECT auth.jwt() AS jwt) -> 'app_metadata'::text) ->> 'role'::text) = 'admin'::text));


--
-- Name: app_credit_costs app_credit_costs_public_read; Type: POLICY; Schema: public; Owner: -
--

CREATE POLICY app_credit_costs_public_read ON public.app_credit_costs FOR SELECT TO authenticated, anon USING ((is_active = true));


--
-- Name: app_credit_costs app_credit_costs_service_all; Type: POLICY; Schema: public; Owner: -
--

CREATE POLICY app_credit_costs_service_all ON public.app_credit_costs TO service_role USING (true) WITH CHECK (true);


--
-- Name: app_sources; Type: ROW SECURITY; Schema: public; Owner: -
--

ALTER TABLE public.app_sources ENABLE ROW LEVEL SECURITY;

--
-- Name: app_sources app_sources_public_read; Type: POLICY; Schema: public; Owner: -
--

CREATE POLICY app_sources_public_read ON public.app_sources FOR SELECT TO authenticated, anon USING (true);


--
-- Name: app_sources app_sources_service_all; Type: POLICY; Schema: public; Owner: -
--

CREATE POLICY app_sources_service_all ON public.app_sources TO service_role USING (true);


--
-- Name: calc_analytics; Type: ROW SECURITY; Schema: public; Owner: -
--

ALTER TABLE public.calc_analytics ENABLE ROW LEVEL SECURITY;

--
-- Name: calc_analytics calc_analytics_admin_read; Type: POLICY; Schema: public; Owner: -
--

CREATE POLICY calc_analytics_admin_read ON public.calc_analytics FOR SELECT TO authenticated USING ((((( SELECT auth.jwt() AS jwt) -> 'app_metadata'::text) ->> 'role'::text) = 'admin'::text));


--
-- Name: calc_analytics calc_analytics_insert_any; Type: POLICY; Schema: public; Owner: -
--

CREATE POLICY calc_analytics_insert_any ON public.calc_analytics FOR INSERT TO authenticated, anon WITH CHECK (true);


--
-- Name: calc_analytics calc_analytics_service_all; Type: POLICY; Schema: public; Owner: -
--

CREATE POLICY calc_analytics_service_all ON public.calc_analytics TO service_role USING (true);


--
-- Name: calc_daily_stats; Type: ROW SECURITY; Schema: public; Owner: -
--

ALTER TABLE public.calc_daily_stats ENABLE ROW LEVEL SECURITY;

--
-- Name: calc_daily_stats calc_daily_stats_admin_read; Type: POLICY; Schema: public; Owner: -
--

CREATE POLICY calc_daily_stats_admin_read ON public.calc_daily_stats FOR SELECT TO authenticated USING ((((( SELECT auth.jwt() AS jwt) -> 'app_metadata'::text) ->> 'role'::text) = 'admin'::text));


--
-- Name: calc_daily_stats calc_daily_stats_service_all; Type: POLICY; Schema: public; Owner: -
--

CREATE POLICY calc_daily_stats_service_all ON public.calc_daily_stats TO service_role USING (true);


--
-- Name: credit_accounts; Type: ROW SECURITY; Schema: public; Owner: -
--

ALTER TABLE public.credit_accounts ENABLE ROW LEVEL SECURITY;

--
-- Name: credit_accounts credit_accounts_owner_select; Type: POLICY; Schema: public; Owner: -
--

CREATE POLICY credit_accounts_owner_select ON public.credit_accounts FOR SELECT TO authenticated USING ((user_id IN ( SELECT users.id
   FROM public.users
  WHERE ((users.auth_user_id)::text = (( SELECT auth.uid() AS uid))::text))));


--
-- Name: credit_accounts credit_accounts_service_all; Type: POLICY; Schema: public; Owner: -
--

CREATE POLICY credit_accounts_service_all ON public.credit_accounts TO service_role USING (true) WITH CHECK (true);


--
-- Name: credit_packages; Type: ROW SECURITY; Schema: public; Owner: -
--

ALTER TABLE public.credit_packages ENABLE ROW LEVEL SECURITY;

--
-- Name: credit_packages credit_packages_admin_all; Type: POLICY; Schema: public; Owner: -
--

CREATE POLICY credit_packages_admin_all ON public.credit_packages TO authenticated USING ((((( SELECT auth.jwt() AS jwt) -> 'app_metadata'::text) ->> 'role'::text) = 'admin'::text)) WITH CHECK ((((( SELECT auth.jwt() AS jwt) -> 'app_metadata'::text) ->> 'role'::text) = 'admin'::text));


--
-- Name: credit_packages credit_packages_public_read; Type: POLICY; Schema: public; Owner: -
--

CREATE POLICY credit_packages_public_read ON public.credit_packages FOR SELECT TO authenticated, anon USING ((is_active = true));


--
-- Name: credit_packages credit_packages_service_all; Type: POLICY; Schema: public; Owner: -
--

CREATE POLICY credit_packages_service_all ON public.credit_packages TO service_role USING (true) WITH CHECK (true);


--
-- Name: credit_transactions; Type: ROW SECURITY; Schema: public; Owner: -
--

ALTER TABLE public.credit_transactions ENABLE ROW LEVEL SECURITY;

--
-- Name: credit_transactions credit_transactions_owner_select; Type: POLICY; Schema: public; Owner: -
--

CREATE POLICY credit_transactions_owner_select ON public.credit_transactions FOR SELECT TO authenticated USING ((user_id IN ( SELECT users.id
   FROM public.users
  WHERE ((users.auth_user_id)::text = (( SELECT auth.uid() AS uid))::text))));


--
-- Name: credit_transactions credit_transactions_service_all; Type: POLICY; Schema: public; Owner: -
--

CREATE POLICY credit_transactions_service_all ON public.credit_transactions TO service_role USING (true) WITH CHECK (true);


--
-- Name: pepti_price_analytics; Type: ROW SECURITY; Schema: public; Owner: -
--

ALTER TABLE public.pepti_price_analytics ENABLE ROW LEVEL SECURITY;

--
-- Name: pepti_price_analytics pepti_price_analytics_admin_read; Type: POLICY; Schema: public; Owner: -
--

CREATE POLICY pepti_price_analytics_admin_read ON public.pepti_price_analytics FOR SELECT TO authenticated USING ((((( SELECT auth.jwt() AS jwt) -> 'app_metadata'::text) ->> 'role'::text) = 'admin'::text));


--
-- Name: pepti_price_analytics pepti_price_analytics_insert_any; Type: POLICY; Schema: public; Owner: -
--

CREATE POLICY pepti_price_analytics_insert_any ON public.pepti_price_analytics FOR INSERT TO authenticated, anon WITH CHECK (true);


--
-- Name: pepti_price_analytics pepti_price_analytics_service_all; Type: POLICY; Schema: public; Owner: -
--

CREATE POLICY pepti_price_analytics_service_all ON public.pepti_price_analytics TO service_role USING (true);


--
-- Name: pepti_price_daily_stats; Type: ROW SECURITY; Schema: public; Owner: -
--

ALTER TABLE public.pepti_price_daily_stats ENABLE ROW LEVEL SECURITY;

--
-- Name: pepti_price_daily_stats pepti_price_daily_stats_admin_read; Type: POLICY; Schema: public; Owner: -
--

CREATE POLICY pepti_price_daily_stats_admin_read ON public.pepti_price_daily_stats FOR SELECT TO authenticated USING ((((( SELECT auth.jwt() AS jwt) -> 'app_metadata'::text) ->> 'role'::text) = 'admin'::text));


--
-- Name: pepti_price_daily_stats pepti_price_daily_stats_service_all; Type: POLICY; Schema: public; Owner: -
--

CREATE POLICY pepti_price_daily_stats_service_all ON public.pepti_price_daily_stats TO service_role USING (true);


--
-- Name: sds_compounds; Type: ROW SECURITY; Schema: public; Owner: -
--

ALTER TABLE public.sds_compounds ENABLE ROW LEVEL SECURITY;

--
-- Name: sds_compounds sds_compounds_public_read; Type: POLICY; Schema: public; Owner: -
--

CREATE POLICY sds_compounds_public_read ON public.sds_compounds FOR SELECT TO authenticated, anon USING (true);


--
-- Name: sds_compounds sds_compounds_service_write; Type: POLICY; Schema: public; Owner: -
--

CREATE POLICY sds_compounds_service_write ON public.sds_compounds TO service_role USING (true);


--
-- Name: sds_documents; Type: ROW SECURITY; Schema: public; Owner: -
--

ALTER TABLE public.sds_documents ENABLE ROW LEVEL SECURITY;

--
-- Name: sds_documents sds_documents_insert_own; Type: POLICY; Schema: public; Owner: -
--

CREATE POLICY sds_documents_insert_own ON public.sds_documents FOR INSERT TO authenticated, anon WITH CHECK (((user_id IS NULL) OR (user_id IN ( SELECT users.id
   FROM public.users
  WHERE ((users.auth_user_id)::text = (( SELECT auth.uid() AS uid))::text)))));


--
-- Name: sds_documents sds_documents_own_or_public; Type: POLICY; Schema: public; Owner: -
--

CREATE POLICY sds_documents_own_or_public ON public.sds_documents FOR SELECT TO authenticated, anon USING (((user_id IS NULL) OR (user_id IN ( SELECT users.id
   FROM public.users
  WHERE ((users.auth_user_id)::text = (( SELECT auth.uid() AS uid))::text)))));


--
-- Name: sds_documents sds_documents_service_all; Type: POLICY; Schema: public; Owner: -
--

CREATE POLICY sds_documents_service_all ON public.sds_documents TO service_role USING (true);


--
-- Name: sds_hazard_data; Type: ROW SECURITY; Schema: public; Owner: -
--

ALTER TABLE public.sds_hazard_data ENABLE ROW LEVEL SECURITY;

--
-- Name: sds_hazard_data sds_hazard_data_public_read; Type: POLICY; Schema: public; Owner: -
--

CREATE POLICY sds_hazard_data_public_read ON public.sds_hazard_data FOR SELECT TO authenticated, anon USING (true);


--
-- Name: sds_hazard_data sds_hazard_data_service_write; Type: POLICY; Schema: public; Owner: -
--

CREATE POLICY sds_hazard_data_service_write ON public.sds_hazard_data TO service_role USING (true);


--
-- Name: sds_job_queue; Type: ROW SECURITY; Schema: public; Owner: -
--

ALTER TABLE public.sds_job_queue ENABLE ROW LEVEL SECURITY;

--
-- Name: sds_job_queue sds_job_queue_insert_own; Type: POLICY; Schema: public; Owner: -
--

CREATE POLICY sds_job_queue_insert_own ON public.sds_job_queue FOR INSERT TO authenticated, anon WITH CHECK (((user_id IS NULL) OR (user_id IN ( SELECT users.id
   FROM public.users
  WHERE ((users.auth_user_id)::text = (( SELECT auth.uid() AS uid))::text)))));


--
-- Name: sds_job_queue sds_job_queue_own_or_public; Type: POLICY; Schema: public; Owner: -
--

CREATE POLICY sds_job_queue_own_or_public ON public.sds_job_queue FOR SELECT TO authenticated, anon USING (((user_id IS NULL) OR (user_id IN ( SELECT users.id
   FROM public.users
  WHERE ((users.auth_user_id)::text = (( SELECT auth.uid() AS uid))::text)))));


--
-- Name: sds_job_queue sds_job_queue_service_all; Type: POLICY; Schema: public; Owner: -
--

CREATE POLICY sds_job_queue_service_all ON public.sds_job_queue TO service_role USING (true);


--
-- Name: sds_pdf_templates; Type: ROW SECURITY; Schema: public; Owner: -
--

ALTER TABLE public.sds_pdf_templates ENABLE ROW LEVEL SECURITY;

--
-- Name: sds_pdf_templates sds_pdf_templates_admin_read; Type: POLICY; Schema: public; Owner: -
--

CREATE POLICY sds_pdf_templates_admin_read ON public.sds_pdf_templates FOR SELECT TO authenticated USING ((((( SELECT auth.jwt() AS jwt) -> 'app_metadata'::text) ->> 'role'::text) = 'admin'::text));


--
-- Name: sds_pdf_templates sds_pdf_templates_service_all; Type: POLICY; Schema: public; Owner: -
--

CREATE POLICY sds_pdf_templates_service_all ON public.sds_pdf_templates TO service_role USING (true);


--
-- Name: sds_pinned_compounds; Type: ROW SECURITY; Schema: public; Owner: -
--

ALTER TABLE public.sds_pinned_compounds ENABLE ROW LEVEL SECURITY;

--
-- Name: sds_pinned_compounds sds_pinned_compounds_public_read; Type: POLICY; Schema: public; Owner: -
--

CREATE POLICY sds_pinned_compounds_public_read ON public.sds_pinned_compounds FOR SELECT TO authenticated, anon USING (true);


--
-- Name: sds_pinned_compounds sds_pinned_compounds_service_write; Type: POLICY; Schema: public; Owner: -
--

CREATE POLICY sds_pinned_compounds_service_write ON public.sds_pinned_compounds TO service_role USING (true);


--
-- Name: sds_sections; Type: ROW SECURITY; Schema: public; Owner: -
--

ALTER TABLE public.sds_sections ENABLE ROW LEVEL SECURITY;

--
-- Name: sds_sections sds_sections_public_read; Type: POLICY; Schema: public; Owner: -
--

CREATE POLICY sds_sections_public_read ON public.sds_sections FOR SELECT TO authenticated, anon USING (true);


--
-- Name: sds_sections sds_sections_service_write; Type: POLICY; Schema: public; Owner: -
--

CREATE POLICY sds_sections_service_write ON public.sds_sections TO service_role USING (true);


--
-- Name: stripe_customers; Type: ROW SECURITY; Schema: public; Owner: -
--

ALTER TABLE public.stripe_customers ENABLE ROW LEVEL SECURITY;

--
-- Name: stripe_customers stripe_customers_owner_select; Type: POLICY; Schema: public; Owner: -
--

CREATE POLICY stripe_customers_owner_select ON public.stripe_customers FOR SELECT TO authenticated USING ((user_id IN ( SELECT users.id
   FROM public.users
  WHERE ((users.auth_user_id)::text = (( SELECT auth.uid() AS uid))::text))));


--
-- Name: stripe_customers stripe_customers_service_all; Type: POLICY; Schema: public; Owner: -
--

CREATE POLICY stripe_customers_service_all ON public.stripe_customers TO service_role USING (true) WITH CHECK (true);


--
-- Name: subscription_events; Type: ROW SECURITY; Schema: public; Owner: -
--

ALTER TABLE public.subscription_events ENABLE ROW LEVEL SECURITY;

--
-- Name: subscription_events subscription_events_admin_select; Type: POLICY; Schema: public; Owner: -
--

CREATE POLICY subscription_events_admin_select ON public.subscription_events FOR SELECT TO authenticated USING ((((( SELECT auth.jwt() AS jwt) -> 'app_metadata'::text) ->> 'role'::text) = 'admin'::text));


--
-- Name: subscription_events subscription_events_service_all; Type: POLICY; Schema: public; Owner: -
--

CREATE POLICY subscription_events_service_all ON public.subscription_events TO service_role USING (true) WITH CHECK (true);


--
-- Name: subscriptions; Type: ROW SECURITY; Schema: public; Owner: -
--

ALTER TABLE public.subscriptions ENABLE ROW LEVEL SECURITY;

--
-- Name: subscriptions subscriptions_admin_select; Type: POLICY; Schema: public; Owner: -
--

CREATE POLICY subscriptions_admin_select ON public.subscriptions FOR SELECT TO authenticated USING ((((( SELECT auth.jwt() AS jwt) -> 'app_metadata'::text) ->> 'role'::text) = 'admin'::text));


--
-- Name: subscriptions subscriptions_owner_select; Type: POLICY; Schema: public; Owner: -
--

CREATE POLICY subscriptions_owner_select ON public.subscriptions FOR SELECT TO authenticated USING ((user_id IN ( SELECT users.id
   FROM public.users
  WHERE ((users.auth_user_id)::text = (( SELECT auth.uid() AS uid))::text))));


--
-- Name: subscriptions subscriptions_service_all; Type: POLICY; Schema: public; Owner: -
--

CREATE POLICY subscriptions_service_all ON public.subscriptions TO service_role USING (true) WITH CHECK (true);


--
-- Name: user_suggestions; Type: ROW SECURITY; Schema: public; Owner: -
--

ALTER TABLE public.user_suggestions ENABLE ROW LEVEL SECURITY;

--
-- Name: user_suggestions user_suggestions_insert_authenticated; Type: POLICY; Schema: public; Owner: -
--

CREATE POLICY user_suggestions_insert_authenticated ON public.user_suggestions FOR INSERT TO authenticated WITH CHECK (true);


--
-- Name: user_suggestions user_suggestions_public_read; Type: POLICY; Schema: public; Owner: -
--

CREATE POLICY user_suggestions_public_read ON public.user_suggestions FOR SELECT TO authenticated, anon USING (true);


--
-- Name: user_suggestions user_suggestions_service_all; Type: POLICY; Schema: public; Owner: -
--

CREATE POLICY user_suggestions_service_all ON public.user_suggestions TO service_role USING (true);


--
-- Name: wiki_coupons wiki_coupons_admin_read; Type: POLICY; Schema: public; Owner: -
--

CREATE POLICY wiki_coupons_admin_read ON public.wiki_coupons FOR SELECT TO authenticated USING ((((( SELECT auth.jwt() AS jwt) -> 'app_metadata'::text) ->> 'role'::text) = 'admin'::text));


--
-- Name: wiki_coupons wiki_coupons_influencer_own; Type: POLICY; Schema: public; Owner: -
--

CREATE POLICY wiki_coupons_influencer_own ON public.wiki_coupons TO authenticated USING ((influencer_id IN ( SELECT users.id
   FROM public.users
  WHERE ((users.auth_user_id)::text = (( SELECT auth.uid() AS uid))::text)))) WITH CHECK ((influencer_id IN ( SELECT users.id
   FROM public.users
  WHERE ((users.auth_user_id)::text = (( SELECT auth.uid() AS uid))::text))));


--
-- Name: wiki_coupons wiki_coupons_public_read_active; Type: POLICY; Schema: public; Owner: -
--

CREATE POLICY wiki_coupons_public_read_active ON public.wiki_coupons FOR SELECT TO authenticated, anon USING (((is_active = true) AND (deleted_at IS NULL)));


--
-- PostgreSQL database dump complete
--

\unrestrict vXMbyM7I8HejD4bN7dtFBxbvXtVwr9fFbADUWnzwmtjpMkmiZAyXXThbcJSg7sh

